"""
拉取用到的库读写：白名单 atlas_pull_whitelist、设置 atlas_settings、每来源状态 fabric_pull_state、
改动记录 atlas_admin_log，以及把一页文档写进 documents。表在 migration/versions/V018__pull_controls.sql。
"""
import json
from contextlib import contextmanager

from sqlalchemy import text

# 设置的默认值（库里没有这一行时用）；管理接口 PUT 会写进 atlas_settings
DEFAULTS = {
    "pull.interval_seconds": 600,   # 两轮之间睡多久
    "pull.paused": False,           # 暂停后服务只空转，不拉
    "pull.run_now": False,          # 置 true 后服务下一次醒来就跑一轮（暂停时也跑），跑完自动清掉
    "quality.min_level": "",        # 最低等级：'' 不限 / 低 / 中 / 高
    "quality.skip_quarantine": True,  # 等级为“隔离”的不进
    "quality.allow_unscored": True,   # fabric 还没打分的放行
}


@contextmanager
def _session():
    from db.session import get_session

    with get_session() as session:
        if session is None:
            raise RuntimeError("数据库未配置（DB_HOST/DB_NAME）")
        yield session


def log_change(session, actor: str, action: str, detail: dict):
    session.execute(text("INSERT INTO atlas_admin_log (actor, action, detail) VALUES (:a, :act, CAST(:d AS jsonb))"),
                    {"a": actor, "act": action, "d": json.dumps(detail, ensure_ascii=False, default=str)})


# ── 设置 ──────────────────────────────────────────────────────────────
def get_settings(prefix: str = "") -> dict:
    with _session() as s:
        stored = {r[0]: r[1] for r in s.execute(text("SELECT key, value FROM atlas_settings"))}
    merged = {**DEFAULTS, **{k: v for k, v in stored.items() if k in DEFAULTS}}
    return {k: v for k, v in merged.items() if k.startswith(prefix)}


def set_settings(values: dict, actor: str):
    with _session() as s:
        for key, value in values.items():
            s.execute(text(
                "INSERT INTO atlas_settings (key, value, updated_by, updated_at) VALUES (:k, CAST(:v AS jsonb), :a, NOW()) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by, "
                "updated_at = NOW()"), {"k": key, "v": json.dumps(value, ensure_ascii=False), "a": actor})
        if actor != "pull-service":
            log_change(s, actor, "settings.update", values)


def quality_gate() -> dict:
    q = get_settings("quality.")
    return {"min_level": q["quality.min_level"], "skip_quarantine": q["quality.skip_quarantine"],
            "allow_unscored": q["quality.allow_unscored"]}


# ── 白名单 ────────────────────────────────────────────────────────────
_WL_COLS = "id, source_id, doc_type, enabled, note, updated_by, updated_at"


def list_whitelist() -> list[dict]:
    with _session() as s:
        return [dict(r) for r in s.execute(text(
            f"SELECT {_WL_COLS} FROM atlas_pull_whitelist ORDER BY source_id, doc_type")).mappings()]


def add_whitelist(row: dict, actor: str) -> dict:
    with _session() as s:
        out = dict(s.execute(text(
            "INSERT INTO atlas_pull_whitelist (source_id, doc_type, enabled, note, updated_by) "
            f"VALUES (:source_id, :doc_type, :enabled, :note, :a) RETURNING {_WL_COLS}"), {**row, "a": actor}
        ).mappings().one())
        log_change(s, actor, "whitelist.add", out)
        return out


def update_whitelist(row_id: int, changes: dict, actor: str) -> dict | None:
    sets = ", ".join(f"{k} = :{k}" for k in changes)
    with _session() as s:
        out = s.execute(text(
            f"UPDATE atlas_pull_whitelist SET {sets}, updated_by = :a, updated_at = NOW() WHERE id = :id "
            f"RETURNING {_WL_COLS}"), {**changes, "a": actor, "id": row_id}).mappings().first()
        if out:
            log_change(s, actor, "whitelist.update", {"id": row_id, **changes})
        return dict(out) if out else None


def delete_whitelist(row_id: int, actor: str) -> bool:
    with _session() as s:
        gone = s.execute(text(f"DELETE FROM atlas_pull_whitelist WHERE id = :id RETURNING {_WL_COLS}"),
                         {"id": row_id}).mappings().first()
        if gone:
            log_change(s, actor, "whitelist.delete", dict(gone))
        return gone is not None


# ── 每来源状态 ────────────────────────────────────────────────────────
def last_seq(source_id: str) -> int:
    with _session() as s:
        row = s.execute(text("SELECT last_seq FROM fabric_pull_state WHERE source_id = :s"), {"s": source_id}).first()
        return row[0] if row else 0


def mark_run(source_id: str, started: bool, error: str | None = None):
    """一个来源这一轮开始（started=True，清掉上次错误）或结束（写结束时间和错误）。"""
    col = "last_started_at" if started else "last_finished_at"
    with _session() as s:
        s.execute(text(
            f"INSERT INTO fabric_pull_state (source_id, {col}, last_error) VALUES (:s, NOW(), :e) "
            f"ON CONFLICT (source_id) DO UPDATE SET {col} = NOW(), "
            "last_error = CASE WHEN :started THEN NULL ELSE :e END"), {"s": source_id, "e": error, "started": started})


def list_state() -> list[dict]:
    with _session() as s:
        return [dict(r) for r in s.execute(text(
            "SELECT source_id, last_seq, max_seq, GREATEST(max_seq - last_seq, 0) AS backlog, skipped_whitelist, "
            "skipped_quality, last_started_at, last_finished_at, last_error, updated_at "
            "FROM fabric_pull_state ORDER BY source_id")).mappings()]


def save_page(source_id: str, rows: list[dict], next_after: int | None, skipped: dict, max_seq: int | None):
    """一页文档 + 序号 + 跳过数在一个事务里写。next_after=None（按需请求）时不动序号。"""
    from db.models import Document

    with _session() as session:
        for row in rows:
            doc = session.query(Document).filter(Document.uuid == row["uuid"]).first()
            if doc is None:
                session.add(Document(**row, extraction_status="pending", weknora_sync_status="pending"))
                continue
            if doc.fabric_version_id == row["fabric_version_id"]:
                continue
            changed = doc.raw_content != row["raw_content"]
            for key, value in row.items():
                setattr(doc, key, value)
            doc.is_deleted = False
            # 正文变了就重新抽取（旧的抽取结果保留，和 /re-extract 一样）；正在抽的不打断
            if changed and doc.extraction_status not in ("queued", "processing"):
                doc.extraction_status = "pending"
        session.execute(text(
            "INSERT INTO fabric_pull_state (source_id, last_seq, max_seq, skipped_whitelist, skipped_quality) "
            "VALUES (:s, COALESCE(:seq, 0), COALESCE(:max, 0), :w, :q) ON CONFLICT (source_id) DO UPDATE SET "
            "last_seq = COALESCE(:seq, fabric_pull_state.last_seq), "
            "max_seq = GREATEST(fabric_pull_state.max_seq, COALESCE(:max, 0)), "
            "skipped_whitelist = fabric_pull_state.skipped_whitelist + :w, "
            "skipped_quality = fabric_pull_state.skipped_quality + :q, updated_at = NOW()"),
            {"s": source_id, "seq": next_after, "max": max_seq, "w": skipped["whitelist"], "q": skipped["quality"]})


def mark_pending(uuids: list[str]):
    """按需请求的文档：内容没变也重新标成待抽取（正在抽的不打断）。"""
    if not uuids:
        return
    with _session() as s:
        s.execute(text("UPDATE documents SET extraction_status = 'pending' WHERE uuid = ANY(:u) "
                       "AND extraction_status NOT IN ('queued', 'processing')"), {"u": uuids})
