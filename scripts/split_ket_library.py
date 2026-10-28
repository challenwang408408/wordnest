#!/usr/bin/env python3
"""按原始 204 项固定搭配来源拆分哥哥 KET 词库，保留词条 ID 和学习记录。

默认只读预检；显式 --apply 才在一个事务中重命名词库并移动关联。
必须明确指定已有数据库、孩子 ID/slug 和原 KET 词库 ID。
不加载 .env、不初始化数据库、不调用网络、不创建或更新单词。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any


DEFAULT_SOURCE = Path(__file__).resolve().parent / "vocabularies" / "ket-sources.json"
ORIGINAL_NAME = "KET词库"
WORDS_NAME = "KET-单词"
PHRASES_NAME = "KET-词组"
PHRASE_DOCUMENT = "ket-204-phrases"
TOTAL_COUNT = 1986
PHRASE_COUNT = 204


class SplitError(ValueError):
    """可安全展示给操作者的迁移校验错误。"""


def load_source(path: Path) -> tuple[set[str], set[str]]:
    """只接受已审阅来源的完整集合与 001 至 204 的原始编号。"""
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("library_name") != ORIGINAL_NAME
        or not isinstance(document.get("entries"), list)
    ):
        raise SplitError("来源格式不符合已审阅的 KET 来源清单")
    entries = document["entries"]
    all_words: set[str] = set()
    phrases: set[str] = set()
    phrase_ids: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise SplitError("来源词条格式无效")
        spelling = entry.get("spelling")
        normalized = entry.get("normalized_spelling")
        sources = entry.get("sources")
        if (
            not isinstance(spelling, str)
            or not isinstance(normalized, str)
            or not normalized
            or normalized != spelling.strip().lower()
            or normalized in all_words
            or not isinstance(sources, list)
            or not sources
            or not all(isinstance(source, dict) for source in sources)
        ):
            raise SplitError("来源词条拼写、唯一性或来源标记无效")
        all_words.add(normalized)
        for source in sources:
            if source.get("document") == PHRASE_DOCUMENT:
                source_id = source.get("source_id")
                if not isinstance(source_id, str):
                    raise SplitError("固定搭配来源编号无效")
                phrase_ids.append(source_id)
                phrases.add(normalized)
    expected_ids = {f"phrases-{number:03d}" for number in range(1, PHRASE_COUNT + 1)}
    if (
        len(all_words) != TOTAL_COUNT
        or len(phrases) != PHRASE_COUNT
        or len(phrase_ids) != PHRASE_COUNT
        or set(phrase_ids) != expected_ids
    ):
        raise SplitError("来源必须恰有 1986 个唯一词条和编号齐全的 204 项固定搭配")
    return all_words, phrases


def _members(
    connection: sqlite3.Connection, library_id: int, profile_id: int,
) -> dict[str, int]:
    rows = connection.execute(
        "SELECT w.id,w.profile_id,w.normalized_spelling FROM library_words lw "
        "JOIN words w ON w.id=lw.word_id WHERE lw.library_id=?", (library_id,),
    ).fetchall()
    if any(row["profile_id"] != profile_id for row in rows):
        raise SplitError("词库含有其他孩子的词条关联，拒绝迁移")
    result = {row["normalized_spelling"]: row["id"] for row in rows}
    if len(result) != len(rows):
        raise SplitError("词库存在重复规范拼写，拒绝迁移")
    return result


def _require_exact(actual: set[str], expected: set[str], label: str) -> None:
    if actual != expected:
        raise SplitError(
            f"{label}集合与来源不一致：缺少 {len(expected - actual)} 项，"
            f"额外 {len(actual - expected)} 项；未作修改"
        )


def _foreign_keys_ok(connection: sqlite3.Connection) -> None:
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise SplitError("数据库外键校验失败，拒绝迁移")


def _protected_snapshot(connection: sqlite3.Connection) -> dict[str, list[tuple[Any, ...]]]:
    """校验所有非词库表，连触发器间接修改也必须回滚。"""
    tables = [row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND name NOT IN ('libraries','library_words')"
    )]
    return {
        table: [tuple(row) for row in connection.execute(
            'SELECT * FROM "' + table.replace('"', '""') + '" ORDER BY rowid'
        )]
        for table in tables
    }


def split_ket_library(
    database: Path, *, profile_id: int, profile_slug: str, library_id: int,
    source: Path = DEFAULT_SOURCE, apply: bool = False,
) -> dict[str, Any]:
    all_words, phrases = load_source(source)
    words = all_words - phrases
    database = database.expanduser().resolve()
    if not database.is_file():
        raise SplitError("目标 SQLite 文件不存在；不会自动创建数据库")
    if profile_id <= 0 or library_id <= 0 or profile_slug != "brother":
        raise SplitError("必须指定哥哥的实际 ID、brother slug 和 KET 词库 ID")
    mode = "rw" if apply else "ro"
    connection = sqlite3.connect(
        database.as_uri() + f"?mode={mode}", uri=True, timeout=30, isolation_level=None,
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        if not apply:
            connection.execute("PRAGMA query_only=ON")
        # 写入锁在读取前获取；并发录入不能落在预检与写入之间。
        connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        _foreign_keys_ok(connection)
        profile = connection.execute(
            "SELECT slug FROM profiles WHERE id=?", (profile_id,),
        ).fetchone()
        if profile is None or profile["slug"] != profile_slug:
            raise SplitError("孩子 ID 与 slug 不匹配，拒绝迁移")
        original = connection.execute(
            "SELECT * FROM libraries WHERE id=? AND profile_id=?", (library_id, profile_id),
        ).fetchone()
        if original is None:
            raise SplitError("目标词库不存在或不属于指定孩子")
        if original["is_default"]:
            raise SplitError("默认词库不能用于本次 KET 拆分")
        targets = {
            row["name"]: row for row in connection.execute(
                "SELECT * FROM libraries WHERE profile_id=? AND name IN (?,?)",
                (profile_id, WORDS_NAME, PHRASES_NAME),
            )
        }
        source_members = _members(connection, library_id, profile_id)
        target_id: int | None = None
        already_split = original["name"] == WORDS_NAME
        if already_split:
            target = targets.get(PHRASES_NAME)
            if target is None or target["is_default"]:
                raise SplitError("已重命名词库缺少有效词组库，拒绝推断或补写")
            target_id = target["id"]
            _require_exact(set(source_members), words, WORDS_NAME)
            _require_exact(set(_members(connection, target_id, profile_id)), phrases, PHRASES_NAME)
        else:
            if original["name"] != ORIGINAL_NAME:
                raise SplitError("词库名称不是原 KET词库 或已完成拆分的 KET-单词")
            if targets:
                raise SplitError("已有同名目标词库冲突，拒绝合并或覆盖")
            _require_exact(set(source_members), all_words, ORIGINAL_NAME)

        report: dict[str, Any] = {
            "status": "already_split" if already_split else "dry_run",
            "applied": False,
            "profile_id": profile_id,
            "profile_slug": profile_slug,
            "words_library_id": library_id,
            "words_library_name": WORDS_NAME,
            "phrases_library_id": target_id,
            "phrases_library_name": PHRASES_NAME,
            "total_entries": len(all_words),
            "word_entries": len(words),
            "phrase_entries": len(phrases),
            "moved_links": 0 if already_split else len(phrases),
            "changed_rows": 0,
        }
        if not apply or already_split:
            connection.rollback()
            return report

        protected = _protected_snapshot(connection)
        other_libraries = [tuple(row) for row in connection.execute(
            "SELECT * FROM libraries WHERE id<>? ORDER BY id", (library_id,),
        )]
        other_links = [tuple(row) for row in connection.execute(
            "SELECT * FROM library_words WHERE library_id<>? ORDER BY library_id,word_id",
            (library_id,),
        )]
        connection.execute(
            "UPDATE libraries SET name=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND profile_id=?",
            (WORDS_NAME, library_id, profile_id),
        )
        cursor = connection.execute(
            "INSERT INTO libraries(profile_id,name,is_default) VALUES(?,?,0)",
            (profile_id, PHRASES_NAME),
        )
        target_id = cursor.lastrowid
        if target_id is None:
            raise SplitError("无法确认新词组库 ID，事务回滚")
        moved = connection.executemany(
            "UPDATE library_words SET library_id=? WHERE library_id=? AND word_id=?",
            [(target_id, library_id, source_members[phrase]) for phrase in sorted(phrases)],
        ).rowcount
        if moved != PHRASE_COUNT:
            raise SplitError("实际移动关联数量不是 204，事务回滚")

        _require_exact(set(_members(connection, library_id, profile_id)), words, WORDS_NAME)
        _require_exact(set(_members(connection, target_id, profile_id)), phrases, PHRASES_NAME)
        _foreign_keys_ok(connection)
        if protected != _protected_snapshot(connection):
            raise SplitError("非词库数据发生变化，事务回滚")
        if other_libraries != [tuple(row) for row in connection.execute(
            "SELECT * FROM libraries WHERE id NOT IN (?,?) ORDER BY id", (library_id, target_id),
        )]:
            raise SplitError("其他词库发生变化，事务回滚")
        if other_links != [tuple(row) for row in connection.execute(
            "SELECT * FROM library_words WHERE library_id NOT IN (?,?) ORDER BY library_id,word_id",
            (library_id, target_id),
        )]:
            raise SplitError("其他词库关联发生变化，事务回滚")
        updated = connection.execute("SELECT * FROM libraries WHERE id=?", (library_id,)).fetchone()
        if updated is None or updated["name"] != WORDS_NAME or any(
            updated[key] != original[key] for key in original.keys() if key not in {"name", "updated_at"}
        ):
            raise SplitError("原词库 ID 或元数据意外变化，事务回滚")
        target = connection.execute("SELECT * FROM libraries WHERE id=?", (target_id,)).fetchone()
        if target is None or (
            target["profile_id"], target["name"], target["is_default"]
        ) != (profile_id, PHRASES_NAME, 0):
            raise SplitError("新词组库归属或元数据无效，事务回滚")
        report.update(
            status="applied", applied=True, phrases_library_id=target_id,
            changed_rows=connection.total_changes,
        )
        connection.commit()
        return report
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="现有 SQLite 数据库文件")
    parser.add_argument("--profile-id", type=int, required=True, help="哥哥的实际 ID")
    parser.add_argument("--profile-slug", required=True, help="必须是 brother，用于再次校验归属")
    parser.add_argument("--library-id", type=int, required=True, help="现有 KET 词库 ID，拆分后保留")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="已审阅的 ket-sources.json")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="提交整个迁移事务")
    mode.add_argument("--dry-run", action="store_true", help="只读预检，与默认行为相同")
    args = parser.parse_args(argv)
    try:
        report = split_ket_library(
            args.database, profile_id=args.profile_id, profile_slug=args.profile_slug,
            library_id=args.library_id, source=args.source, apply=args.apply,
        )
    except (SplitError, OSError, UnicodeError, json.JSONDecodeError, sqlite3.Error) as exc:
        # 不输出数据库原始异常、词条正文或 SQL 参数。
        message = str(exc) if isinstance(exc, SplitError) else "读取或迁移失败；事务未提交"
        print(f"失败：{message}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
