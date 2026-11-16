"""
从资料库（fabric）拉文档到 Atlas 自己的 documents 表（本地缓存），抽取流程只读这张表。

做法：
  1. 来源：FABRIC_SOURCES（逗号分隔）；留空就问 GET /api/fabric/sources 要全部可读来源。
  2. 每个来源从 fabric_pull_state 里记的序号接着翻：GET /api/fabric/changes?source_id=&is_demo=false&after=&limit=
  3. 每页的版本再取清洗正文：GET /api/fabric/clean-text?version_ids=...（还没洗好的就用版本自带的 clean_text）。
  4. 一页写一次库：documents 按 (来源, 记录号) 一行，新版本覆盖旧内容并把 extraction_status 改回 pending；
     同一事务里记下拉到的序号。中途失败，下次从上一页接着拉。

用法:
    python fabric_pull.py                  # 拉全部来源的新版本
    python fabric_pull.py --source nmpa    # 只拉一个来源
    python fabric_pull.py --dry-run        # 只打印，不写库
"""
import argparse
import uuid as _uuid
from datetime import datetime, timedelta, timezone

import httpx
from loguru import logger

from config.settings import APP

PAGE = 100  # fabric 一页最多 100 条


def document_uuid(source_id: str, source_record_id: str) -> str:
    """同一条来源记录始终是同一个文档 uuid（新版本覆盖旧版本）。"""
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"fabric:{source_id}:{source_record_id}"))


def map_document(source_id: str, item: dict, clean: dict | None) -> dict:
    """fabric 的一个版本（changes 的 item）+ 它的清洗结果（clean-text 的一项）→ documents 表的字段。"""
    clean = clean or {}
    processed = clean.get("state") == "processed"
    text = (clean.get("clean") or {}).get("text") if processed else None
    profile = clean.get("profile") or {}
    when = item.get("source_published_at") or item.get("event_time") or {}
    return {
        "uuid": document_uuid(source_id, item["source_record_id"]),
        "fabric_version_id": item["version_id"],
        "title": item.get("title") or "",
        "source_url": item.get("source_url") or "",
        "source_site": source_id,
        "raw_content": text if text is not None else (item.get("clean_text") or ""),
        "publish_date": when.get("value") or "",
        "doc_type": profile.get("doc_type") or item.get("record_kind") or "",
        "category": profile.get("doc_category") or "",
        "language": (clean.get("clean") or {}).get("language") or "",
        "parse_method": "fabric_clean_text" if processed else "fabric_version_text",
        "crawl_timestamp": datetime.fromisoformat(item["first_seen_at"]) if item.get("first_seen_at") else None,
    }


def pull_source(client, source_id: str, after: int, save, max_pages: int = 0) -> int:
    """从序号 after 往后翻页；每页调用 save(rows, next_after)。返回最后拉到的序号。"""
    pages = 0
    while True:
        page = client.get("/api/fabric/changes", params={
            "source_id": source_id, "is_demo": "false", "after": after, "limit": PAGE}).json()
        items = page.get("items") or []
        if items:
            cutoff = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
            cleans = client.get("/api/fabric/clean-text", params={
                "source_id": source_id, "is_demo": "false", "mode": "current", "cutoff": cutoff,
                "version_ids": [i["version_id"] for i in items]}).json().get("versions", {})
            rows = [map_document(source_id, i, cleans.get(i["version_id"])) for i in items]
        else:
            rows = []
        next_after = int(page.get("next_after", after))
        if rows or next_after != after:
            save(rows, next_after)
        logger.info(f"[fabric] {source_id}: after={after} → {next_after}，本页 {len(rows)} 条")
        pages += 1
        done = next_after <= after or next_after >= int(page.get("max_seq", next_after))
        if done or (max_pages and pages >= max_pages):
            return next_after
        after = next_after


def _save_to_db(source_id: str):
    """返回一个 save 函数：一页文档和序号在同一个事务里写进库。"""
    from db.models import Document, FabricPullState
    from db.session import get_session

    def save(rows, next_after):
        with get_session() as session:
            if session is None:
                raise RuntimeError("数据库未配置（DB_HOST/DB_NAME）")
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
            state = session.get(FabricPullState, source_id)
            if state is None:
                session.add(FabricPullState(source_id=source_id, last_seq=next_after))
            else:
                state.last_seq = next_after
    return save


def _last_seq(source_id: str) -> int:
    from db.models import FabricPullState
    from db.session import get_session

    with get_session() as session:
        if session is None:
            raise RuntimeError("数据库未配置（DB_HOST/DB_NAME）")
        state = session.get(FabricPullState, source_id)
        return state.last_seq if state else 0


def main():
    parser = argparse.ArgumentParser(description="从资料库拉文档到 Atlas 的 documents 表")
    parser.add_argument("--source", default="", help="只拉这个来源")
    parser.add_argument("--max-pages", type=int, default=0, help="每个来源最多翻几页（0 = 翻完）")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写库")
    args = parser.parse_args()

    headers = {"Authorization": f"Bearer {APP.FABRIC_READ_TOKEN}"}
    with httpx.Client(base_url=APP.FABRIC_API_URL, headers=headers, timeout=60) as client:
        client.event_hooks["response"] = [lambda r: r.raise_for_status()]
        if args.source:
            sources = [args.source]
        elif APP.FABRIC_SOURCES:
            sources = [s.strip() for s in APP.FABRIC_SOURCES.split(",") if s.strip()]
        else:
            sources = [s["source_id"] for s in client.get("/api/fabric/sources").json()["sources"]]
        for source_id in sources:
            after = 0 if args.dry_run else _last_seq(source_id)
            save = (lambda rows, seq: None) if args.dry_run else _save_to_db(source_id)
            last = pull_source(client, source_id, after, save, args.max_pages)
            logger.info(f"[fabric] {source_id} 拉到序号 {last}")


if __name__ == "__main__":
    main()
