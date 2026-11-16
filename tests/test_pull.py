"""pull/：字段映射、翻页、两道关、按需请求、服务循环（假的 HTTP 客户端，不连库不联网）。"""
import threading
from types import SimpleNamespace

from pull import fabric, service

ITEM = {"source_id": "nmpa", "source_record_id": "R1", "version_id": "a" * 64, "record_kind": "regulatory_notice",
        "title": "某药获批", "source_url": "https://example.org/1", "clean_text": "版本自带正文",
        "source_published_at": {"value": "2026-10-01", "precision": "day"},
        "first_seen_at": "2026-10-02T00:00:00+00:00", "published_seq": 7}
RULES = [{"source_id": "nmpa", "doc_type": "", "enabled": True}]
GATE = {"min_level": "", "skip_quarantine": True, "allow_unscored": True}


def _resp(data):
    return SimpleNamespace(json=lambda: data)


def test_map_document_prefers_clean_text_and_falls_back():
    clean = {"state": "processed", "clean": {"text": "清洗正文", "language": "zh"},
             "profile": {"doc_type": "drug_approval", "doc_category": "regulatory"}}
    row = fabric.map_document("nmpa", ITEM, clean)
    assert row["raw_content"] == "清洗正文" and row["language"] == "zh"
    assert row["doc_type"] == "drug_approval" and row["publish_date"] == "2026-10-01"
    assert row["uuid"] == fabric.document_uuid("nmpa", "R1") and row["source_site"] == "nmpa"

    fallback = fabric.map_document("nmpa", ITEM, {"state": "not_processed"})
    assert fallback["raw_content"] == "版本自带正文" and fallback["doc_type"] == "regulatory_notice"


def test_pull_source_pages_until_max_seq():
    pages = {0: {"items": [ITEM], "next_after": 7, "max_seq": 9},
             7: {"items": [dict(ITEM, version_id="b" * 64, published_seq=9)], "next_after": 9, "max_seq": 9}}

    class Client:
        def get(self, path, params):
            return _resp(pages[params["after"]] if path.endswith("/changes") else {"versions": {}})

    saved = []
    last = fabric.pull_source(Client(), "nmpa", 0, lambda rows, seq, sk, mx: saved.append((len(rows), seq, mx)),
                              RULES, GATE)
    assert last == 9 and saved == [(1, 7, 9), (1, 9, 9)]


def test_whitelist_skips_and_counts():
    rules = [{"source_id": "nmpa", "doc_type": "drug_approval", "enabled": True},
             {"source_id": "pubmed", "doc_type": "", "enabled": False}]
    assert fabric.allowed_by_whitelist(rules, "nmpa", "drug_approval")
    assert not fabric.allowed_by_whitelist(rules, "nmpa", "regulatory_notice")
    assert not fabric.allowed_by_whitelist(rules, "pubmed", "article")
    rows, skipped = fabric.filter_page("nmpa", [ITEM], {}, rules, GATE)  # 没画像，类型是 regulatory_notice
    assert rows == [] and skipped == {"whitelist": 1, "quality": 0}


def test_quality_gate():
    assert fabric.allowed_by_quality(None, GATE)  # 拿不到分放行
    assert not fabric.allowed_by_quality(None, {**GATE, "allow_unscored": False})
    assert not fabric.allowed_by_quality({"level": "隔离"}, GATE)
    assert fabric.allowed_by_quality({"level": "隔离"}, {**GATE, "skip_quarantine": False})
    assert not fabric.allowed_by_quality({"level": "低"}, {**GATE, "min_level": "中"})
    assert fabric.allowed_by_quality({"level": "高"}, {**GATE, "min_level": "中"})
    rows, skipped = fabric.filter_page("nmpa", [ITEM], {ITEM["version_id"]: {"quality": {"level": "隔离"}}},
                                       RULES, GATE)
    assert rows == [] and skipped == {"whitelist": 0, "quality": 1}


def test_request_versions_bypasses_whitelist_keeps_quality_unless_forced():
    vid, bad = "c" * 64, "d" * 64

    class Client:
        def get(self, path, params):
            if path.endswith("/clean-text"):
                assert params["quality"] == "true"
                return _resp({"versions": {vid: {"state": "not_processed", "source_record_id": "R9",
                                                 "quality": {"level": "隔离"}},
                                           bad: {"state": "not_visible_or_not_processed"}}})
            assert path == f"/api/fabric/versions/{vid}" and params["source_record_id"] == "R9"
            return _resp(dict(ITEM, version_id=vid, source_record_id="R9"))

    rows, skipped, missing = fabric.request_versions(Client(), "pubmed", [vid, bad], GATE)
    assert rows == [] and skipped["quality"] == 1 and missing == [bad]
    rows, _, _ = fabric.request_versions(Client(), "pubmed", [vid], GATE, force=True)
    assert [r["fabric_version_id"] for r in rows] == [vid] and rows[0]["source_site"] == "pubmed"


def test_run_forever_respects_pause_run_now_and_stop():
    stop = threading.Event()
    state = {"pull.paused": True, "pull.run_now": True, "pull.interval_seconds": 600}
    rounds = []

    def round_fn(_stop):
        rounds.append(1)
        stop.set()

    service.run_forever(stop, round_fn, lambda _p: dict(state), lambda: state.update({"pull.run_now": False}),
                        tick=0)
    assert rounds == [1] and state["pull.run_now"] is False  # 暂停中“立即跑一轮”也跑，跑完清标志
