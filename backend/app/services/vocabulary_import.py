"""预检并以一个事务导入已经补全的词库。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)
from sqlalchemy import MetaData, Table, func, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class VocabularyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    spelling: RequiredText = Field(max_length=120)
    meaning_zh: RequiredText = Field(max_length=255)
    part_of_speech: RequiredText = Field(max_length=64)
    ipa: RequiredText = Field(max_length=120)
    syllables: RequiredText = Field(max_length=160)
    example_en: RequiredText
    example_zh: RequiredText

    @property
    def normalized_spelling(self) -> str:
        # 与 api.deps.normalize_spelling 完全一致，避免为已有词生成另一份记录。
        return self.spelling.strip().lower()


class VocabularyDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: int = Field(ge=1, le=1)
    library_name: RequiredText = Field(max_length=120)
    expected_count: int = Field(gt=0)
    entries: list[VocabularyEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def check_count_and_duplicates(self) -> VocabularyDocument:
        if len(self.entries) != self.expected_count:
            raise ValueError("entries 条数必须与 expected_count 完全一致")
        seen: set[str] = set()
        for index, entry in enumerate(self.entries, start=1):
            key = entry.normalized_spelling
            if key in seen:
                raise ValueError(f"第 {index} 条与前面的 normalized_spelling 重复")
            seen.add(key)
        return self


@dataclass(frozen=True)
class VocabularyImportResult:
    profile_id: int
    library_id: int | None
    library_name: str
    total_entries: int
    new_words: int
    existing_words: int
    new_links: int
    already_linked: int
    will_create_library: bool
    library_total_after: int
    applied: bool


class VocabularyImportError(ValueError):
    """输入或目标数据库不满足安全导入条件。"""


def validate_document(document: object) -> VocabularyDocument:
    try:
        # 重新验证模型实例，调用方不能用 model_construct 绕过字段检查。
        raw = (
            document.model_dump()
            if isinstance(document, VocabularyDocument)
            else document
        )
        return VocabularyDocument.model_validate(raw)
    except ValidationError as exc:
        details = []
        for issue in exc.errors(include_input=False, include_url=False)[:10]:
            location = ".".join(str(part) for part in issue["loc"]) or "document"
            details.append(f"{location}: {issue['msg']}")
        raise VocabularyImportError("输入校验失败；" + "；".join(details)) from exc


def _import_in_transaction(
    conn: Connection,
    document: VocabularyDocument,
    profile_id: int,
    apply: bool,
) -> VocabularyImportResult:
    # 反射现有表，不导入会读取 .env 的应用配置，也不创建/迁移目标数据库。
    metadata = MetaData()
    tables = {
        name: Table(name, metadata, autoload_with=conn, resolve_fks=False)
        for name in ("profiles", "libraries", "words", "library_words", "word_progress")
    }
    profiles, libraries, words, links, progress = (
        tables[name]
        for name in ("profiles", "libraries", "words", "library_words", "word_progress")
    )
    if conn.scalar(select(profiles.c.id).where(profiles.c.id == profile_id)) is None:
        raise VocabularyImportError("目标孩子不存在；不会自动新建孩子")
    library = (
        conn.execute(
            select(libraries.c.id, libraries.c.profile_id).where(
                libraries.c.profile_id == profile_id,
                libraries.c.name == document.library_name,
            )
        )
        .mappings()
        .one_or_none()
    )
    library_id = int(library["id"]) if library is not None else None
    will_create_library = library is None
    if library is not None and library["profile_id"] != profile_id:
        raise VocabularyImportError("已有词库的孩子归属不匹配")

    linked_ids: set[int] = set()
    if library_id is not None:
        for linked in conn.execute(
            select(links.c.word_id, words.c.profile_id)
            .select_from(links.outerjoin(words, links.c.word_id == words.c.id))
            .where(links.c.library_id == library_id)
        ).mappings():
            if linked["profile_id"] != profile_id:
                raise VocabularyImportError(
                    "已有词库含有归属异常的单词，请先修复后重试"
                )
            linked_ids.add(int(linked["word_id"]))

    existing_words = {
        row["normalized_spelling"]: int(row["id"])
        for row in conn.execute(
            select(words.c.id, words.c.normalized_spelling).where(
                words.c.profile_id == profile_id
            )
        ).mappings()
    }
    existing_count = sum(
        entry.normalized_spelling in existing_words for entry in document.entries
    )
    already_linked = sum(
        existing_words.get(entry.normalized_spelling) in linked_ids
        for entry in document.entries
    )
    new_links = document.expected_count - already_linked

    if apply:
        if library_id is None:
            inserted = conn.execute(
                libraries.insert().values(
                    profile_id=profile_id,
                    name=document.library_name,
                    is_default=False,
                )
            )
            library_id = int(inserted.inserted_primary_key[0])
        for entry in document.entries:
            word_id = existing_words.get(entry.normalized_spelling)
            if word_id is None:
                inserted = conn.execute(
                    words.insert().values(
                        profile_id=profile_id,
                        normalized_spelling=entry.normalized_spelling,
                        **entry.model_dump(),
                        is_mastered=False,
                    )
                )
                word_id = int(inserted.inserted_primary_key[0])
                conn.execute(
                    progress.insert().values(
                        profile_id=profile_id,
                        word_id=word_id,
                        familiarity=0,
                        correct_streak=0,
                        review_count=0,
                    )
                )
            if word_id not in linked_ids:
                conn.execute(
                    links.insert().values(library_id=library_id, word_id=word_id)
                )

        linked_count = conn.scalar(
            select(func.count())
            .select_from(links)
            .where(links.c.library_id == library_id)
        )
        if linked_count != len(linked_ids) + new_links:
            raise VocabularyImportError("导入后的关联数量异常；本次写入已回滚")

    return VocabularyImportResult(
        profile_id=profile_id,
        library_id=library_id,
        library_name=document.library_name,
        total_entries=document.expected_count,
        new_words=document.expected_count - existing_count,
        existing_words=existing_count,
        new_links=new_links,
        already_linked=already_linked,
        will_create_library=will_create_library,
        library_total_after=len(linked_ids) + new_links,
        applied=apply,
    )


def import_vocabulary(
    engine: Engine,
    document: object,
    *,
    profile_id: int,
    apply: bool = False,
) -> VocabularyImportResult:
    """默认仅查询预检；apply=True 时在独立事务中提交，任意异常全量回滚。

    调用方传入 Engine，本服务独立管理连接和事务，不会提交调用方 Session 的改动。
    输入必须是完整词条；既有词只增词库关联，全部内容、状态和历史保持原样。
    """
    validated = validate_document(document)
    if type(profile_id) is not int or profile_id <= 0:
        raise VocabularyImportError("必须明确指定有效的孩子 profile_id")
    if type(apply) is not bool:
        raise VocabularyImportError("apply 必须是布尔值")
    try:
        with engine.begin() as conn:
            return _import_in_transaction(conn, validated, profile_id, apply)
    except SQLAlchemyError as exc:
        message = (
            "导入失败，事务已回滚；请检查数据库结构和约束"
            if apply
            else "预检失败，未写入；请检查目标数据库结构"
        )
        raise VocabularyImportError(message) from exc
