"""
从资料库（fabric）拉文档到 Atlas 的 documents 表（本地缓存），抽取流程只读这张表。

一页的做法：
  1. GET /api/fabric/changes?source_id=&is_demo=false&after=&limit=  某来源在序号之后的新版本。
  2. GET /api/fabric/clean-text?...&quality=true  这些版本的清洗正文、画像和质量分。
  3. 过两道关：第 1 关来源/类型白名单（allowed_by_whitelist），第 2 关质量分门槛（allowed_by_quality）；
     没过的不进 documents，只记跳过数。第 3 关是抽取后的分流（disambiguation/routing.py），不在这里。
  4. save(rows, next_after, skipped, max_seq)：一页文档和序号在同一个事务里写库（pull/store.py）。
"""
import uuid as _uuid
from datetime import datetime, timedelta, timezone

from loguru import logger

PAGE = 100  # fabric 一页最多 100 条
LEVELS = {"隔离": 0, "低": 1, "中": 2, "高": 3}  # fabric clean-text?quality=true 的 level（由画像折算，fabric clean/profile.py quality_level）


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


# ── 第 1 关：来源/类型白名单（表 atlas_pull_whitelist，管理接口可改） ──────────
def allowed_by_whitelist(rules: list[dict], source_id: str, doc_type: str) -> bool:
    """有一条启用的规则对上来源，且规则没写类型或类型相同，就放行。"""
    return any(r["enabled"] and r["source_id"] == source_id and (not r.get("doc_type") or r["doc_type"] == doc_type)
               for r in rules)


# ── 第 2 关：质量分门槛（atlas_settings 的 quality.*，管理接口可改） ──────────
def allowed_by_quality(quality: dict | None, gate: dict) -> bool:
    """quality 是 fabric clean-text?quality=true 给的 {score, level, ...}；还没打分是 None。
    拿不到分时按 gate["allow_unscored"] 决定（默认放行）。"""
    if not quality or quality.get("level") not in LEVELS:
        return gate.get("allow_unscored", True)
    level = quality["level"]
    if level == "隔离" and gate.get("skip_quarantine", True):
        return False
    min_level = gate.get("min_level") or ""
    return not (min_level in LEVELS and LEVELS[level] < LEVELS[min_level])


def fetch_cleans(client, source_id: str, version_ids: list[str]) -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    return client.get("/api/fabric/clean-text", params={
        "source_id": source_id, "is_demo": "false", "mode": "current", "cutoff": cutoff, "quality": "true",
        "version_ids": version_ids}).json().get("versions", {})


def filter_page(source_id: str, items: list[dict], cleans: dict, rules: list[dict] | None, gate: dict):
    """一页版本过两道关。rules=None 表示绕过白名单（按需请求）。返回 (rows, skipped)。"""
    rows, skipped = [], {"whitelist": 0, "quality": 0}
    for item in items:
        clean = cleans.get(item["version_id"])
        row = map_document(source_id, item, clean)
        if rules is not None and not allowed_by_whitelist(rules, source_id, row["doc_type"]):
            skipped["whitelist"] += 1
        elif not allowed_by_quality((clean or {}).get("quality"), gate):
            skipped["quality"] += 1
        else:
            rows.append(row)
    return rows, skipped


def pull_source(client, source_id: str, after: int, save, rules: list[dict], gate: dict, max_pages: int = 0,
                should_stop=lambda: False) -> int:
    """从序号 after 往后翻页；每页调用 save(rows, next_after, skipped, max_seq)。返回最后拉到的序号。"""
    pages = 0
    while True:
        page = client.get("/api/fabric/changes", params={
            "source_id": source_id, "is_demo": "false", "after": after, "limit": PAGE}).json()
        items = page.get("items") or []
        cleans = fetch_cleans(client, source_id, [i["version_id"] for i in items]) if items else {}
        rows, skipped = filter_page(source_id, items, cleans, rules, gate)
        next_after = int(page.get("next_after", after))
        max_seq = int(page.get("max_seq", next_after))
        if items or next_after != after:
            save(rows, next_after, skipped, max_seq)
        logger.info(f"[pull] {source_id}: after={after} → {next_after}，进 {len(rows)} 条，跳过 {skipped}")
        pages += 1
        done = next_after <= after or next_after >= max_seq
        if done or (max_pages and pages >= max_pages) or should_stop():
            return next_after
        after = next_after


def request_versions(client, source_id: str, version_ids: list[str], gate: dict, force: bool = False):
    """按需请求：绕过白名单，按版本号取一批（≤100）。force=True 连质量门槛也绕过。
    fabric 没有“只凭版本号取版本”的接口，所以要带 source_id：clean-text 给记录号，再逐个取 /versions/{id}。
    返回 (rows, skipped, missing)。"""
    cleans = fetch_cleans(client, source_id, version_ids)
    items, missing = [], []
    for vid in version_ids:
        meta = cleans.get(vid) or {}
        if not meta.get("source_record_id"):
            missing.append(vid)
            continue
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        version = client.get(f"/api/fabric/versions/{vid}", params={
            "source_id": source_id, "source_record_id": meta["source_record_id"], "is_demo": "false",
            "mode": "current", "cutoff": cutoff}).json()
        items.append({**version, "version_id": vid, "source_record_id": meta["source_record_id"],
                      "first_seen_at": version.get("first_seen_at") or meta.get("first_seen_at")})
    gate = {"allow_unscored": True, "skip_quarantine": False, "min_level": ""} if force else gate
    rows, skipped = filter_page(source_id, items, cleans, None, gate)
    return rows, skipped, missing
