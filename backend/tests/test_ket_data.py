"""KET发布词库必须覆盖冻结来源，订正可追踪，重合词不复制学习记录。"""
import json
from collections import Counter
from pathlib import Path

from backend.app.services.vocabulary_import import validate_document

ROOT = Path(__file__).resolve().parents[2] / "scripts" / "vocabularies"


def test_ket_data_covers_both_frozen_sources():
    source = json.loads((ROOT / "ket-sources.json").read_text())
    document = validate_document(json.loads((ROOT / "ket.json").read_text()))
    assert document.library_name == source["library_name"] == "KET词库"
    assert document.expected_count == len(source["entries"]) == 1986
    entries = {row.normalized_spelling: row for row in document.entries}
    assert set(entries) == {row["normalized_spelling"] for row in source["entries"]}
    cambridge_keys, phrase_keys, source_ids = set(), set(), set()
    for row in source["entries"]:
        assert row["spelling"].strip().lower() == row["normalized_spelling"]
        assert row["sources"]
        for ref in row["sources"]:
            source_ids.add(ref["source_id"])
            if ref["document"] == "cambridge-a2-key-2025-08":
                assert 4 <= ref["page"] <= 32
                cambridge_keys.add(row["normalized_spelling"])
            else:
                assert ref["document"] == "ket-204-phrases"
                assert 1 <= ref["page"] <= 9
                phrase_keys.add(row["normalized_spelling"])
    assert len(cambridge_keys) == 1807
    assert len(phrase_keys) == 204
    assert len(cambridge_keys & phrase_keys) == 25
    assert {f"phrases-{i:03}" for i in range(1, 205)} <= source_ids
    assert {f"cambridge-2025-{i:04}" for i in range(1, 1729)} <= source_ids
    assert Counter(row["content_origin"] == "existing-word" for row in source["entries"]) == {
        True: 951,
        False: 1035,
    }
    legacy_syllables = source["retained_legacy_syllable_format"]
    assert legacy_syllables == {"as well": "as · well", "make sure": "make · sure", "awesome": "aw·some"}
    for row in document.entries:
        if row.normalized_spelling in legacy_syllables:
            assert row.syllables == legacy_syllables[row.normalized_spelling]
        else:
            assert row.syllables.replace("·", "").lower() == row.normalized_spelling
        assert row.ipa.startswith("/") and row.ipa.endswith("/")
        for text in (row.meaning_zh, row.example_zh):
            assert any("\u4e00" <= character <= "\u9fff" for character in text)
            assert "待补" not in text and "TODO" not in text


def test_ket_phrase_corrections_preserve_original_trace():
    source = json.loads((ROOT / "ket-sources.json").read_text())
    phrase_refs = {
        ref["source_id"]: (row["normalized_spelling"], ref)
        for row in source["entries"]
        for ref in row["sources"]
        if ref["document"] == "ket-204-phrases"
    }
    assert phrase_refs["phrases-132"][0] == "make up"
    assert phrase_refs["phrases-134"][0] == "make up for"
    assert phrase_refs["phrases-134"][1]["original_spelling"] == "make up"
    assert phrase_refs["phrases-159"][0] == "send for"
    assert phrase_refs["phrases-159"][1]["original_spelling"] == "sent for"
    assert phrase_refs["phrases-160"][0] == "send out"
    assert phrase_refs["phrases-004"][0] == "arrive"
    assert phrase_refs["phrases-156"][0] == "provide for"
