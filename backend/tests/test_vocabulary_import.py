from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from backend.app import database
from backend.app.models import Library, LibraryWord, ReviewEvent, Word
from backend.app.services.vocabulary_import import (
    VocabularyImportError,
    import_vocabulary,
)


def entry(spelling: str = "apple") -> dict[str, str]:
    return {
        "spelling": spelling,
        "meaning_zh": "苹果",
        "part_of_speech": "名词",
        "ipa": "/ˈæpəl/",
        "syllables": "ap·ple",
        "example_en": "An apple grows on this tree.",
        "example_zh": "这棵树上长着一个苹果。",
    }


def document(*spellings: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "library_name": "小学单词",
        "expected_count": len(spellings),
        "entries": [entry(spelling) for spelling in spellings],
    }


def snapshot() -> dict[str, list[tuple[object, ...]]]:
    """比较持久化行，包含所有旧字段、时间戳和事件。"""
    with database.engine.connect() as conn:
        return {
            name: [tuple(row) for row in conn.execute(text(f"SELECT * FROM {name}"))]
            for name in (
                "profiles",
                "libraries",
                "words",
                "library_words",
                "word_progress",
                "review_events",
                "profile_settings",
            )
        }


def test_import_preserves_existing_word_and_history(
    auth_client: TestClient,
    profiles: dict[str, int],
) -> None:
    pid = profiles["brother"]
    old = auth_client.post(
        f"/api/wordnest/profiles/{pid}/words",
        json={**entry("Apple"), "meaning_zh": "家长原来的苹果释义"},
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
    result = import_vocabulary(
        database.engine,
        document("apple", "book"),
        profile_id=pid,
        apply=True,
    )
    assert result.new_words == 1
    assert result.existing_words == 1
    assert result.new_links == 2
    after = snapshot()
    assert [row for row in after["words"] if row[0] == old["id"]] == before["words"]
    assert after["review_events"] == before["review_events"]
    old_progress = [row for row in after["word_progress"] if row[2] == old["id"]]
    assert old_progress == before["word_progress"]
    assert set(before["library_words"]).issubset(after["library_words"])
    with database.SessionLocal() as db:
        assert db.get(Library, result.library_id).profile_id == pid
        new_word = db.scalar(select(Word).where(Word.normalized_spelling == "book"))
        assert new_word.progress.review_count == 0
        assert new_word.progress.profile_id == pid


def test_default_dry_run_writes_nothing(profiles: dict[str, int]) -> None:
    before = snapshot()
    result = import_vocabulary(
        database.engine,
        document("apple", "book"),
        profile_id=profiles["brother"],
    )
    assert result.applied is False
    assert result.new_words == 2
    assert result.new_links == 2
    assert result.library_id is None
    assert snapshot() == before


def test_second_import_is_idempotent(profiles: dict[str, int]) -> None:
    payload = document("apple", "book")
    first = import_vocabulary(
        database.engine, payload, profile_id=profiles["brother"], apply=True
    )
    before = snapshot()
    second = import_vocabulary(
        database.engine, payload, profile_id=profiles["brother"], apply=True
    )
    assert second.library_id == first.library_id
    assert second.new_words == second.new_links == 0
    assert second.already_linked == second.existing_words == 2
    assert snapshot() == before


def test_same_library_name_and_word_are_separate_per_profile(
    profiles: dict[str, int],
) -> None:
    first = import_vocabulary(
        database.engine, document("apple"), profile_id=profiles["sister"], apply=True
    )
    before = snapshot()
    second = import_vocabulary(
        database.engine, document("apple"), profile_id=profiles["brother"], apply=True
    )
    assert second.library_id != first.library_id
    assert second.new_words == 1
    with database.SessionLocal() as db:
        words = list(db.scalars(select(Word)).all())
        assert len(words) == 2
        assert {word.profile_id for word in words} == set(profiles.values())
        assert len({word.id for word in words}) == 2
    after = snapshot()
    for table in ("words", "libraries", "word_progress", "library_words"):
        assert set(before[table]).issubset(after[table])


@pytest.mark.parametrize("field", list(entry()))
@pytest.mark.parametrize("empty", ["", " \t\n", None])
def test_empty_fields_rejected_before_writing(
    profiles: dict[str, int],
    field: str,
    empty: str | None,
) -> None:
    payload = document("apple", "book")
    payload["entries"][1][field] = empty
    before = snapshot()
    with pytest.raises(VocabularyImportError):
        import_vocabulary(
            database.engine, payload, profile_id=profiles["brother"], apply=True
        )
    assert snapshot() == before


@pytest.mark.parametrize(
    "change", ["duplicate", "count", "version", "extra", "boolean_count", "missing"]
)
def test_invalid_document_rejected(profiles: dict[str, int], change: str) -> None:
    payload = document("apple", "book")
    if change == "duplicate":
        payload["entries"][1]["spelling"] = " APPLE "
    elif change == "count":
        payload["expected_count"] = 3
    elif change == "version":
        payload["schema_version"] = 2
    elif change == "extra":
        payload["entries"][1]["profile_id"] = profiles["sister"]
    elif change == "boolean_count":
        payload["expected_count"] = True
    else:
        del payload["entries"][1]["ipa"]
    before = snapshot()
    with pytest.raises(VocabularyImportError):
        import_vocabulary(
            database.engine, payload, profile_id=profiles["brother"], apply=True
        )
    assert snapshot() == before


def test_unknown_profile_is_not_created(profiles: dict[str, int]) -> None:
    before = snapshot()
    with pytest.raises(VocabularyImportError, match="孩子"):
        import_vocabulary(
            database.engine, document("apple"), profile_id=999, apply=True
        )
    assert snapshot() == before


def test_failure_after_first_insert_rolls_back_entire_import(
    profiles: dict[str, int],
) -> None:
    before = snapshot()
    with database.engine.begin() as conn:
        conn.execute(
            text("""
            CREATE TRIGGER fail_second_word BEFORE INSERT ON words
            WHEN NEW.normalized_spelling = 'book'
            BEGIN SELECT RAISE(ABORT, 'simulated database failure'); END
        """)
        )
    with pytest.raises(VocabularyImportError, match="回滚"):
        import_vocabulary(
            database.engine,
            document("apple", "book"),
            profile_id=profiles["brother"],
            apply=True,
        )
    assert snapshot() == before


def test_existing_library_with_foreign_profile_link_is_rejected(
    profiles: dict[str, int],
) -> None:
    sister = import_vocabulary(
        database.engine, document("apple"), profile_id=profiles["sister"], apply=True
    )
    with database.SessionLocal() as db:
        word_id = db.scalar(
            select(Word.id).where(Word.profile_id == profiles["sister"])
        )
        wrong = Library(
            profile_id=profiles["brother"], name="小学单词", is_default=False
        )
        db.add(wrong)
        db.flush()
        db.add(LibraryWord(library_id=wrong.id, word_id=word_id))
        db.commit()
    before = snapshot()
    with pytest.raises(VocabularyImportError, match="归属"):
        import_vocabulary(
            database.engine,
            document("apple"),
            profile_id=profiles["brother"],
            apply=True,
        )
    assert snapshot() == before
    assert sister.library_id is not None


def test_wrong_answers_across_libraries_accumulate_for_same_word(
    auth_client: TestClient,
    profiles: dict[str, int],
) -> None:
    pid = profiles["brother"]
    base = f"/api/wordnest/profiles/{pid}"
    original = auth_client.post(f"{base}/words", json=entry()).json()
    old_library = original["library_ids"][0]
    result = import_vocabulary(
        database.engine, document("apple"), profile_id=pid, apply=True
    )
    for library_id in (old_library, result.library_id):
        quiz = auth_client.post(
            f"{base}/quiz/start", json={"library_ids": [library_id]}
        ).json()
        assert quiz["total"] == 1
        assert quiz["words"][0]["id"] == original["id"]
        response = auth_client.post(
            f"{base}/quiz/{original['id']}/rate", json={"rating": "unknown"}
        )
        assert response.status_code == 200
    for library_id in (old_library, result.library_id):
        rows = auth_client.get(
            f"{base}/words", params={"library_id": library_id}
        ).json()
        assert rows[0]["id"] == original["id"]
        assert rows[0]["wrong_count"] == 2
        assert rows[0]["progress"]["review_count"] == 2
    preview = auth_client.post(
        f"{base}/quiz/preview",
        json={"library_ids": [old_library, result.library_id]},
    ).json()
    assert preview["available_count"] == 1
    with database.SessionLocal() as db:
        events = list(db.scalars(select(ReviewEvent)).all())
        assert len(events) == 2
        assert {item.word_id for item in events} == {original["id"]}


def test_cli_requires_target_and_never_reads_dotenv(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "import_vocabulary.py"
    payload = document("apple")
    source = tmp_path / "source.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / ".env").write_text(
        "DATABASE_URL=sqlite:///do-not-create.db\n", encoding="utf-8"
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"DATABASE_URL", "DATA_DIR"}
    }
    completed = subprocess.run(
        [sys.executable, str(script), str(source), "--profile-id", "1"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert not (tmp_path / "do-not-create.db").exists()


def test_cli_default_dry_run_and_explicit_apply(
    profiles: dict[str, int],
    db_path: Path,
    tmp_path: Path,
) -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "import_vocabulary.py"
    payload = document(*(f"word {number}" for number in range(1587)))
    source = tmp_path / "full.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    command = [
        sys.executable,
        str(script),
        str(source),
        "--profile-id",
        str(profiles["brother"]),
        "--database-url",
        f"sqlite:///{db_path}",
    ]
    before = snapshot()
    preview = subprocess.run(
        command, cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert preview.returncode == 0, preview.stderr
    assert json.loads(preview.stdout)["applied"] is False
    assert snapshot() == before
    applied = subprocess.run(
        command + ["--apply"], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert applied.returncode == 0, applied.stderr
    assert json.loads(applied.stdout)["new_words"] == 1587
    assert len(snapshot()["words"]) == 1587


@pytest.mark.parametrize(
    "failure", ["missing_database", "wrong_count", "missing_profile"]
)
def test_cli_fails_closed_before_writing(
    profiles: dict[str, int],
    db_path: Path,
    tmp_path: Path,
    failure: str,
) -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "import_vocabulary.py"
    source = tmp_path / "small.json"
    payload = document("apple")
    if failure == "wrong_count":
        payload["expected_count"] = 2
    source.write_text(json.dumps(payload), encoding="utf-8")
    target = tmp_path / "mistyped.db" if failure == "missing_database" else db_path
    command = [
        sys.executable,
        str(script),
        str(source),
        "--database-path",
        str(target),
        "--apply",
    ]
    if failure != "missing_profile":
        command += ["--profile-id", str(profiles["brother"])]
    before = snapshot()
    completed = subprocess.run(
        command, cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert completed.returncode != 0
    assert snapshot() == before
    if failure == "missing_database":
        assert not target.exists()
