"""fabric_pull.py：字段映射和翻页（假的 HTTP 客户端，不连库不联网）。"""
from types import SimpleNamespace

import fabric_pull

ITEM = {"source_id": "nmpa", "source_record_id": "R1", "version_id": "a" * 64, "record_kind": "regulatory_notice",
        "title": "某药获批", "source_url": "https://example.org/1", "clean_text": "版本自带正文",
        "source_published_at": {"value": "2026-10-01", "precision": "day"},
        "first_seen_at": "2026-10-02T00:00:00+00:00", "published_seq": 7}


def test_map_document_prefers_clean_text_and_falls_back():
    clean = {"state": "processed", "clean": {"text": "清洗正文", "language": "zh"},
             "profile": {"doc_type": "drug_approval", "doc_category": "regulatory"}}
    row = fabric_pull.map_document("nmpa", ITEM, clean)
    assert row["raw_content"] == "清洗正文" and row["language"] == "zh"
    assert row["doc_type"] == "drug_approval" and row["publish_date"] == "2026-10-01"
    assert row["uuid"] == fabric_pull.document_uuid("nmpa", "R1") and row["source_site"] == "nmpa"

    fallback = fabric_pull.map_document("nmpa", ITEM, {"state": "not_processed"})
    assert fallback["raw_content"] == "版本自带正文" and fallback["doc_type"] == "regulatory_notice"


def test_pull_source_pages_until_max_seq():
    pages = {0: {"items": [ITEM], "next_after": 7, "max_seq": 9},
             7: {"items": [dict(ITEM, version_id="b" * 64, published_seq=9)], "next_after": 9, "max_seq": 9}}

    class Client:
        def get(self, path, params):
            if path.endswith("/changes"):
                return SimpleNamespace(json=lambda: pages[params["after"]])
            return SimpleNamespace(json=lambda: {"versions": {}})

    saved = []
    last = fabric_pull.pull_source(Client(), "nmpa", 0, lambda rows, seq: saved.append((len(rows), seq)))
    assert last == 9 and saved == [(1, 7), (1, 9)]
