from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from backend.app import database


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "import_vocabulary.py"


def vocabulary_entry(spelling: str) -> dict[str, str]:
    return {
        "spelling": spelling,
        "meaning_zh": "测试词义",
        "part_of_speech": "名词",
        "ipa": "/test/",
        "syllables": spelling,
        "example_en": "This is a test word.",
        "example_zh": "这是一个测试单词。",
    }


def write_vocabulary(tmp_path: Path, count: int) -> Path:
    payload = {
        "schema_version": 1,
        "library_name": "KET 词库",
        "expected_count": count,
        "entries": [vocabulary_entry(f"test word {i}") for i in range(count)],
    }
    source = tmp_path / "ket.json"
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return source


def run_cli(
    source: Path, db_path: Path, profile_id: int, *options: str
) -> subprocess.CompletedProcess[str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"DATABASE_URL", "DATA_DIR", "AI_BUILDER_TOKEN"}
    }
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(source),
            "--database-path",
            str(db_path),
            "--profile-id",
            str(profile_id),
            *options,
        ],
        cwd=source.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def snapshot() -> dict[str, list[tuple[object, ...]]]:
    with database.engine.connect() as connection:
        return {
            name: [
                tuple(row)
                for row in connection.execute(text(f"SELECT * FROM {name} ORDER BY rowid"))
            ]
            for name in database.Base.metadata.tables
        }


@pytest.mark.parametrize("count", [1, 1600])
def test_cli_accepts_reviewed_libraries_with_other_declared_counts(
    profiles: dict[str, int], db_path: Path, tmp_path: Path, count: int
) -> None:
    source = write_vocabulary(tmp_path, count)
    before = snapshot()

    preview = run_cli(source, db_path, profiles["brother"])
    assert preview.returncode == 0, preview.stderr
    report = json.loads(preview.stdout)
    assert report["library_name"] == "KET 词库"
    assert report["total_entries"] == count
    assert report["new_words"] == report["new_links"] == count
    assert report["applied"] is False
    assert snapshot() == before

    applied = run_cli(source, db_path, profiles["brother"], "--apply")
    assert applied.returncode == 0, applied.stderr
    assert json.loads(applied.stdout)["applied"] is True
    after = snapshot()
    assert len(after["words"]) == count
    assert len(after["library_words"]) == count

    repeated = run_cli(source, db_path, profiles["brother"], "--apply")
    assert repeated.returncode == 0, repeated.stderr
    report = json.loads(repeated.stdout)
    assert report["new_words"] == report["new_links"] == 0
    assert report["already_linked"] == count
    assert snapshot() == after


@pytest.mark.parametrize("declared_count", [0, 1, 3, True, "2"])
def test_cli_still_rejects_invalid_declared_counts_before_writing(
    profiles: dict[str, int],
    db_path: Path,
    tmp_path: Path,
    declared_count: object,
) -> None:
    source = write_vocabulary(tmp_path, 2)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["expected_count"] = declared_count
    source.write_text(json.dumps(payload), encoding="utf-8")
    before = snapshot()

    result = run_cli(source, db_path, profiles["brother"], "--apply")

    assert result.returncode != 0
    assert "输入校验失败" in result.stderr
    assert snapshot() == before


def test_cli_links_existing_words_without_changing_either_childs_history(
    auth_client: TestClient,
    profiles: dict[str, int],
    db_path: Path,
    tmp_path: Path,
) -> None:
    source = write_vocabulary(tmp_path, 2)
    for slug, pid in profiles.items():
        old = auth_client.post(
            f"/api/wordnest/profiles/{pid}/words",
            json={
                **vocabulary_entry("Test Word 0"),
                "meaning_zh": f"{slug}原来的释义",
            },
        ).json()
        auth_client.post(
            f"/api/wordnest/profiles/{pid}/quiz/{old['id']}/rate",
            json={"rating": "unknown"},
        )
        auth_client.patch(
            f"/api/wordnest/profiles/{pid}/words/{old['id']}",
            json={"is_mastered": True},
        )
    before = snapshot()

    result = run_cli(source, db_path, profiles["brother"], "--apply")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["new_words"] == 1
    assert report["existing_words"] == 1
    assert report["new_links"] == 2
    after = snapshot()
    for table, rows in before.items():
        assert set(rows).issubset(after[table]), table
    assert after["review_events"] == before["review_events"]
    with database.engine.connect() as connection:
        linked = connection.execute(
            text(
                "SELECT w.profile_id, w.normalized_spelling FROM words w "
                "JOIN library_words lw ON lw.word_id=w.id WHERE lw.library_id=:id"
            ),
            {"id": report["library_id"]},
        ).all()
    assert set(linked) == {
        (profiles["brother"], "test word 0"),
        (profiles["brother"], "test word 1"),
    }


def test_cli_does_not_create_an_unknown_profile_for_a_valid_small_library(
    profiles: dict[str, int], db_path: Path, tmp_path: Path
) -> None:
    source = write_vocabulary(tmp_path, 2)
    before = snapshot()

    result = run_cli(source, db_path, max(profiles.values()) + 1, "--apply")

    assert result.returncode != 0
    assert "目标孩子不存在" in result.stderr
    assert snapshot() == before
