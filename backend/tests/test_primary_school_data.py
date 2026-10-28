"""固定教材词库必须保留来源的全部词头和可用于学习的完整字段。"""
import json
from collections import Counter
from pathlib import Path

from backend.app.services.vocabulary_import import validate_document


def test_primary_school_data_matches_frozen_source():
    root = Path(__file__).resolve().parents[2] / "scripts" / "vocabularies"
    source = json.loads((root / "primary-school-sources.json").read_text())["entries"]
    document = validate_document(json.loads((root / "primary-school.json").read_text()))
    assert document.library_name == "小学单词"
    assert document.expected_count == len(source) == 1587
    assert Counter(row["kind"] for row in source) == {"word": 1099, "phrase": 488}
    assert [row.spelling for row in document.entries] == [row["spelling"] for row in source]
    for row in document.entries:
        assert row.syllables.replace("·", "").lower() == row.spelling.lower()
        assert row.ipa.startswith("/") and row.ipa.endswith("/")
        assert "待补" not in row.example_zh
        assert any("\u4e00" <= character <= "\u9fff" for character in row.example_zh)
