#!/usr/bin/env python3
"""导入已经审阅的完整词库。默认预检；显式 --apply 才写入已有数据库。

python scripts/import_vocabulary.py vocabulary.json --profile-id 1 \
    --database-path /path/to/wordnest.db
确认预检后，在同一命令末尾加 --apply。
JSON 中的 expected_count 必须是正整数，且与 entries 实际条数完全一致。
本脚本不读取 .env、不初始化数据库、不调用 AI，也不输出凭据或词条正文。
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.vocabulary_import import (  # noqa: E402
    VocabularyImportError,
    import_vocabulary,
    validate_document,
)

def existing_database_url(args: argparse.Namespace) -> URL:
    if args.database_path:
        url = URL.create(
            "sqlite", database=str(Path(args.database_path).expanduser().resolve())
        )
    else:
        raw = args.database_url or os.environ.get("DATABASE_URL")
        if not raw and os.environ.get("DATA_DIR"):
            path = Path(os.environ["DATA_DIR"]).expanduser().resolve() / "wordnest.db"
            url = URL.create("sqlite", database=str(path))
        elif raw:
            url = make_url(raw)
        else:
            raise VocabularyImportError(
                "必须用 --database-path、--database-url 或环境变量明确指定现有数据库"
            )
    if url.get_backend_name() != "sqlite":
        raise VocabularyImportError("当前导入器只支持词芽使用的 SQLite 数据库")
    # 不接受内存库或 URI 变体，确保打错路径时不会悄悄创建一个空数据库。
    if url.query or not url.database or url.database == ":memory:":
        raise VocabularyImportError(
            "请指定现有 SQLite 文件路径，不支持内存数据库或 URI 参数"
        )
    path = Path(url.database).expanduser().resolve()
    if not path.is_file():
        raise VocabularyImportError("目标 SQLite 文件不存在；不会自动创建空数据库")
    return URL.create("sqlite", database=str(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="schema_version=1 的完整 JSON 文件")
    parser.add_argument(
        "--profile-id", type=int, required=True, help="目标孩子的实际 ID"
    )
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--database-path", help="现有 wordnest.db 的路径")
    target.add_argument("--database-url", help="现有数据库的 SQLite URL")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="显式提交整个导入事务")
    mode.add_argument("--dry-run", action="store_true", help="仅预检，与默认行为相同")
    args = parser.parse_args(argv)
    try:
        url = existing_database_url(args)
        raw = json.loads(args.source.read_text(encoding="utf-8-sig"))
        payload = validate_document(raw)
        # mode=rw/ro 在连接层再次保证文件必须已经存在，避免检查后的路径竞态。
        mode_name = "rw" if args.apply else "ro"
        uri = Path(url.database).as_uri() + f"?mode={mode_name}"
        engine = create_engine(
            URL.create("sqlite", database=uri, query={"uri": "true"}),
            future=True,
        )

        @event.listens_for(engine, "connect")
        def set_foreign_keys(connection, _record) -> None:  # type: ignore[no-untyped-def]
            connection.execute("PRAGMA foreign_keys=ON")

        try:
            result = import_vocabulary(
                engine, payload, profile_id=args.profile_id, apply=args.apply
            )
        finally:
            engine.dispose()
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return 0
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        VocabularyImportError,
        SQLAlchemyError,
    ) as exc:
        # SQLAlchemy 原始异常可能带 SQL 参数；不打印正文或连接凭据。
        message = (
            str(exc)
            if isinstance(exc, VocabularyImportError)
            else "无法读取输入或连接目标数据库；未完成导入"
        )
        print(f"失败：{message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
