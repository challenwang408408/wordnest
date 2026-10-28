from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from sqlalchemy import create_engine

from backend.app.database import Base


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "split_ket_library.py"
SOURCE = ROOT / "scripts" / "vocabularies" / "ket-sources.json"
DOCUMENT = json.loads(SOURCE.read_text(encoding="utf-8"))
ALL_WORDS = {entry["normalized_spelling"] for entry in DOCUMENT["entries"]}
PHRASES = {
    entry["normalized_spelling"]
    for entry in DOCUMENT["entries"]
    if any(source["document"] == "ket-204-phrases" for source in entry["sources"])
}
WORDS = ALL_WORDS - PHRASES


@pytest.fixture()
def ket_database(tmp_path: Path) -> Path:
    path = tmp_path / "family.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executemany(
            "INSERT INTO profiles(id,slug,display_name) VALUES(?,?,?)",
            [(1, "brother", "哥哥"), (2, "sister", "妹妹")],
        )
        connection.executemany(
            "INSERT INTO libraries(id,profile_id,name,is_default) VALUES(?,?,?,?)",
            [
                (1, 1, "日常阅读", 1),
                (2, 2, "日常阅读", 1),
                (3, 1, "小学单词", 0),
                (4, 1, "KET词库", 0),
                (5, 2, "KET-词组", 0),
            ],
        )
        rows = [
            (index, 1, spelling, spelling, "原来的释义", "动词", "/test/",
             spelling, "Original example.", "原来的例句", index % 2)
            for index, spelling in enumerate(sorted(ALL_WORDS), start=101)
        ]
        rows.append(
            (9000, 2, "arrive", "Arrive", "妹妹的释义", "动词", "/test/",
             "ar·rive", "Original example.", "妹妹的例句", 1)
        )
        connection.executemany(
            "INSERT INTO words(id,profile_id,normalized_spelling,spelling,meaning_zh,"
            "part_of_speech,ipa,syllables,example_en,example_zh,is_mastered) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)", rows,
        )
        arrive_id = next(row[0] for row in rows if row[1] == 1 and row[2] == "arrive")
        connection.executemany(
            "INSERT INTO library_words(library_id,word_id) VALUES(?,?)",
            [(4, row[0]) for row in rows if row[1] == 1]
            + [(1, arrive_id), (3, arrive_id), (2, 9000), (5, 9000)],
        )
        connection.executemany(
            "INSERT INTO word_progress(profile_id,word_id,familiarity,correct_streak,"
            "review_count,last_rating,last_reviewed_at,next_review_at) "
            "VALUES(?,?,3,2,7,'unknown','2026-10-01','2026-10-19')",
            [(1, arrive_id), (2, 9000)],
        )
        connection.executemany(
            "INSERT INTO review_events(profile_id,word_id,rating,reviewed_at) "
            "VALUES(?,?,'unknown','2026-10-01')", [(1, arrive_id), (2, 9000)],
        )
        connection.executemany(
            "INSERT INTO profile_settings(profile_id,daily_quiz_count) VALUES(?,?)",
            [(1, 30), (2, 10)],
        )
    return path


def run_split(path: Path, *options: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--database", str(path), "--profile-id", "1",
         "--profile-slug", "brother", "--library-id", "4", *options],
        cwd=path.parent,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def snapshot(path: Path) -> dict[str, list[tuple[object, ...]]]:
    with sqlite3.connect(path) as connection:
        return {
            table: connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
            for table in Base.metadata.tables
        }


def library_words(path: Path, library_id: int) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {
            row[0] for row in connection.execute(
                "SELECT w.normalized_spelling FROM words w JOIN library_words lw "
                "ON lw.word_id=w.id WHERE lw.library_id=?", (library_id,),
            )
        }


def test_split_restores_original_204_phrases_and_preserves_all_word_history(
    ket_database: Path,
) -> None:
    before = snapshot(ket_database)

    result = run_split(ket_database, "--apply")

    assert result.returncode == 0, result.stderr
    after = snapshot(ket_database)
    source = next(row for row in after["libraries"] if row[0] == 4)
    assert source[2] == "KET-单词"
    target = next(
        row for row in after["libraries"] if row[1] == 1 and row[2] == "KET-词组"
    )
    assert target[3] == 0
    assert library_words(ket_database, 4) == WORDS
    assert library_words(ket_database, target[0]) == PHRASES
    assert "arrive" in library_words(ket_database, target[0])
    assert any(" " in word for word in library_words(ket_database, 4))
    for table in before.keys() - {"libraries", "library_words"}:
        assert after[table] == before[table], table
    assert [row for row in before["libraries"] if row[0] != 4] == [
        row for row in after["libraries"] if row[0] not in (4, target[0])
    ]
    assert [row for row in before["library_words"] if row[0] != 4] == [
        row for row in after["library_words"] if row[0] not in (4, target[0])
    ]
    report = json.loads(result.stdout)
    assert report["status"] == "applied"
    assert report["moved_links"] == 204
    assert report["word_entries"] == 1782
    assert report["phrase_entries"] == 204
    with sqlite3.connect(ket_database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_default_dry_run_is_read_only_and_reports_the_exact_plan(ket_database: Path) -> None:
    before = snapshot(ket_database)
    raw_before = ket_database.read_bytes()
    result = run_split(ket_database)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "dry_run"
    assert report["applied"] is False
    assert report["changed_rows"] == 0
    assert report["moved_links"] == 204
    assert report["phrases_library_id"] is None
    assert snapshot(ket_database) == before
    assert ket_database.read_bytes() == raw_before


def test_repeating_success_is_a_zero_change_noop(ket_database: Path) -> None:
    first = run_split(ket_database, "--apply")
    assert first.returncode == 0, first.stderr
    before = snapshot(ket_database)
    raw_before = ket_database.read_bytes()
    for options in [(), ("--apply",)]:
        result = run_split(ket_database, *options)
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert report["status"] == "already_split"
        assert report["changed_rows"] == report["moved_links"] == 0
        assert snapshot(ket_database) == before
        assert ket_database.read_bytes() == raw_before


@pytest.mark.parametrize(
    "options", [
        ("--profile-id", "2"), ("--profile-slug", "sister"),
        ("--library-id", "2"), ("--library-id", "999"),
    ],
)
def test_wrong_profile_or_library_is_rejected_without_writes(
    ket_database: Path, options: tuple[str, ...],
) -> None:
    before = snapshot(ket_database)
    result = run_split(ket_database, "--apply", *options)
    assert result.returncode != 0
    assert snapshot(ket_database) == before


def test_default_library_cannot_be_repurposed(ket_database: Path) -> None:
    with sqlite3.connect(ket_database) as connection:
        connection.execute("UPDATE libraries SET is_default=1 WHERE id=4")
    before = snapshot(ket_database)
    result = run_split(ket_database, "--apply")
    assert result.returncode != 0
    assert "默认" in result.stderr
    assert snapshot(ket_database) == before


@pytest.mark.parametrize("name", ["KET-词组", "KET-单词"])
def test_existing_target_name_is_a_conflict_even_if_empty(
    ket_database: Path, name: str,
) -> None:
    with sqlite3.connect(ket_database) as connection:
        connection.execute(
            "INSERT INTO libraries(profile_id,name,is_default) VALUES(1,?,0)", (name,),
        )
    before = snapshot(ket_database)
    result = run_split(ket_database, "--apply")
    assert result.returncode != 0
    assert "冲突" in result.stderr
    assert snapshot(ket_database) == before


@pytest.mark.parametrize("change", ["missing", "extra", "wrong_owner", "same_count_different_word"])
def test_source_membership_drift_and_cross_profile_words_fail_closed(
    ket_database: Path, change: str,
) -> None:
    with sqlite3.connect(ket_database) as connection:
        if change == "missing":
            connection.execute("DELETE FROM library_words WHERE library_id=4 AND word_id=101")
        elif change == "extra":
            connection.execute("INSERT INTO library_words VALUES(4,9000)")
        elif change == "wrong_owner":
            connection.execute("UPDATE words SET profile_id=2 WHERE id=101")
        else:
            connection.execute("UPDATE words SET normalized_spelling='unexpected' WHERE id=101")
    before = snapshot(ket_database)
    result = run_split(ket_database, "--apply")
    assert result.returncode != 0
    assert snapshot(ket_database) == before


def test_existing_foreign_key_error_is_rejected_without_repairing_other_data(
    ket_database: Path,
) -> None:
    with sqlite3.connect(ket_database) as connection:
        connection.execute("INSERT INTO library_words VALUES(1,99999)")
    before = snapshot(ket_database)
    result = run_split(ket_database, "--apply")
    assert result.returncode != 0
    assert "外键" in result.stderr
    assert snapshot(ket_database) == before


def test_transaction_failure_rolls_back_rename_creation_and_all_moves(ket_database: Path) -> None:
    with sqlite3.connect(ket_database) as connection:
        connection.execute(
            "CREATE TRIGGER reject_move BEFORE UPDATE ON library_words "
            "WHEN OLD.library_id=4 BEGIN SELECT RAISE(ABORT,'simulated failure'); END"
        )
    before = snapshot(ket_database)
    result = run_split(ket_database, "--apply")
    assert result.returncode != 0
    assert snapshot(ket_database) == before


def test_trigger_that_changes_learning_data_is_detected_and_rolled_back(ket_database: Path) -> None:
    with sqlite3.connect(ket_database) as connection:
        connection.execute(
            "CREATE TRIGGER corrupt_progress AFTER UPDATE ON library_words "
            "WHEN OLD.library_id=4 BEGIN UPDATE word_progress SET review_count=0; END"
        )
    before = snapshot(ket_database)
    result = run_split(ket_database, "--apply")
    assert result.returncode != 0
    assert snapshot(ket_database) == before


def test_corrupted_completed_split_is_not_treated_as_idempotent(ket_database: Path) -> None:
    result = run_split(ket_database, "--apply")
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(ket_database) as connection:
        connection.execute(
            "DELETE FROM library_words WHERE library_id="
            "(SELECT id FROM libraries WHERE profile_id=1 AND name='KET-词组') "
            "AND word_id=(SELECT id FROM words WHERE profile_id=1 AND normalized_spelling='arrive')"
        )
    before = snapshot(ket_database)
    result = run_split(ket_database, "--apply")
    assert result.returncode != 0
    assert snapshot(ket_database) == before


@pytest.mark.parametrize("apply", [False, True])
def test_missing_database_is_never_created(tmp_path: Path, apply: bool) -> None:
    path = tmp_path / "missing.db"
    result = run_split(path, *(('--apply',) if apply else ()))
    assert result.returncode != 0
    assert not path.exists()


@pytest.mark.parametrize("change", ["missing_phrase", "duplicate_id", "duplicate_word"])
def test_invalid_source_is_rejected_before_any_write(
    ket_database: Path, tmp_path: Path, change: str,
) -> None:
    document = json.loads(SOURCE.read_text(encoding="utf-8"))
    phrase_entries = [
        entry for entry in document["entries"]
        if any(source["document"] == "ket-204-phrases" for source in entry["sources"])
    ]
    if change == "missing_phrase":
        phrase_entries[0]["sources"] = [
            source for source in phrase_entries[0]["sources"]
            if source["document"] != "ket-204-phrases"
        ]
    elif change == "duplicate_id":
        for source in phrase_entries[0]["sources"]:
            if source["document"] == "ket-204-phrases":
                source["source_id"] = "phrases-001"
    else:
        document["entries"][1] = document["entries"][0]
    source_path = tmp_path / "invalid-source.json"
    source_path.write_text(json.dumps(document), encoding="utf-8")
    before = snapshot(ket_database)
    result = run_split(ket_database, "--apply", "--source", str(source_path))
    assert result.returncode != 0
    assert snapshot(ket_database) == before
