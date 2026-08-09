from __future__ import annotations

import re

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.api.deps import (
    ensure_libraries_belong,
    get_profile_or_404,
    get_word_for_profile,
    normalize_spelling,
    sync_word_libraries,
    word_to_out,
)
from backend.app.auth import AuthDep, DbDep, SettingsDep
from backend.app.models import LibraryWord, Word, WordProgress
from backend.app.schemas import (
    EnrichBatchRequest,
    EnrichBatchResult,
    EnrichRequest,
    EnrichResult,
    MessageOut,
    ScanResult,
    WordBatchCreate,
    WordBatchOut,
    WordCreate,
    WordOut,
    WordUpdate,
)
from backend.app.services.ai_builder import get_ai_client
from backend.app.services.image_prep import InvalidImageError, prepare_image_data_url

router = APIRouter(prefix="/profiles/{profile_id}/words", tags=["words"])


def _create_or_link_without_commit(
    db: DbDep,
    profile_id: int,
    body: WordCreate,
) -> Word:
    libraries = ensure_libraries_belong(db, profile_id, body.library_ids)
    normalized = normalize_spelling(body.spelling)
    existing = db.scalar(
        select(Word)
        .where(
            Word.profile_id == profile_id,
            Word.normalized_spelling == normalized,
        )
        .options(selectinload(Word.library_words), selectinload(Word.progress))
    )
    if existing is not None:
        from backend.app.models import Library

        all_libs: dict[int, Library] = {}
        for lw in existing.library_words:
            lib = db.get(Library, lw.library_id)
            if lib is not None:
                all_libs[lib.id] = lib
        for lib in libraries:
            all_libs[lib.id] = lib
        sync_word_libraries(db, existing, list(all_libs.values()))
        return existing

    word = Word(
        profile_id=profile_id,
        normalized_spelling=normalized,
        spelling=body.spelling.strip(),
        meaning_zh=body.meaning_zh.strip(),
        part_of_speech=body.part_of_speech.strip(),
        ipa=body.ipa.strip(),
        syllables=body.syllables.strip(),
        example_en=body.example_en.strip(),
        example_zh=body.example_zh.strip(),
        is_mastered=body.is_mastered,
    )
    db.add(word)
    db.flush()
    sync_word_libraries(db, word, libraries)
    db.add(WordProgress(profile_id=profile_id, word_id=word.id))
    return word


@router.get("", response_model=list[WordOut])
def list_words(
    profile_id: int,
    _auth: AuthDep,
    db: DbDep,
    q: str | None = None,
    library_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[WordOut]:
    get_profile_or_404(db, profile_id)
    stmt = (
        select(Word)
        .where(Word.profile_id == profile_id)
        .options(selectinload(Word.library_words), selectinload(Word.progress))
        .order_by(Word.updated_at.desc())
    )
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            (Word.normalized_spelling.like(like)) | (Word.meaning_zh.like(f"%{q.strip()}%"))
        )
    if library_id is not None:
        stmt = stmt.join(LibraryWord).where(LibraryWord.library_id == library_id)
    if status_filter == "mastered":
        stmt = stmt.where(Word.is_mastered.is_(True))
    elif status_filter == "learning":
        stmt = stmt.where(Word.is_mastered.is_(False))
    words = list(db.scalars(stmt).unique().all())
    return [word_to_out(w) for w in words]


@router.post("", response_model=WordOut, status_code=status.HTTP_201_CREATED)
def create_or_link_word(
    profile_id: int,
    body: WordCreate,
    _auth: AuthDep,
    db: DbDep,
) -> WordOut:
    get_profile_or_404(db, profile_id)
    word = _create_or_link_without_commit(db, profile_id, body)
    db.commit()
    return word_to_out(get_word_for_profile(db, profile_id, word.id))


@router.post("/batch", response_model=WordBatchOut, status_code=status.HTTP_201_CREATED)
def create_or_link_words_batch(
    profile_id: int,
    body: WordBatchCreate,
    _auth: AuthDep,
    db: DbDep,
) -> WordBatchOut:
    get_profile_or_404(db, profile_id)
    try:
        words = [
            _create_or_link_without_commit(db, profile_id, item)
            for item in body.items
        ]
        word_ids = [word.id for word in words]
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="批量保存失败，本次没有写入任何单词",
        ) from exc
    return WordBatchOut(
        items=[
            word_to_out(get_word_for_profile(db, profile_id, word_id))
            for word_id in word_ids
        ]
    )


@router.patch("/{word_id}", response_model=WordOut)
def update_word(
    profile_id: int,
    word_id: int,
    body: WordUpdate,
    _auth: AuthDep,
    db: DbDep,
) -> WordOut:
    word = get_word_for_profile(db, profile_id, word_id)
    data = body.model_dump(exclude_unset=True)
    library_ids = data.pop("library_ids", None)
    if "spelling" in data and data["spelling"] is not None:
        word.spelling = data["spelling"].strip()
        word.normalized_spelling = normalize_spelling(word.spelling)
    for field in (
        "meaning_zh",
        "part_of_speech",
        "ipa",
        "syllables",
        "example_en",
        "example_zh",
    ):
        if field in data and data[field] is not None:
            setattr(word, field, str(data[field]).strip())
    if "is_mastered" in data and data["is_mastered"] is not None:
        word.is_mastered = bool(data["is_mastered"])
    if library_ids is not None:
        libraries = ensure_libraries_belong(db, profile_id, library_ids)
        sync_word_libraries(db, word, libraries)
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="保存失败，可能和其他单词拼写冲突",
        ) from exc
    return word_to_out(get_word_for_profile(db, profile_id, word_id))


@router.delete("/{word_id}", response_model=MessageOut)
def delete_word(
    profile_id: int,
    word_id: int,
    _auth: AuthDep,
    db: DbDep,
) -> MessageOut:
    word = get_word_for_profile(db, profile_id, word_id)
    db.delete(word)
    db.commit()
    return MessageOut(message="单词已删除")


@router.post("/enrich", response_model=EnrichResult)
def enrich_word(
    profile_id: int,
    body: EnrichRequest,
    _auth: AuthDep,
    db: DbDep,
    settings: SettingsDep,
) -> EnrichResult:
    get_profile_or_404(db, profile_id)
    client = get_ai_client(settings)
    return client.enrich_word(body.spelling)


@router.post("/enrich-batch", response_model=EnrichBatchResult)
def enrich_words_batch(
    profile_id: int,
    body: EnrichBatchRequest,
    _auth: AuthDep,
    db: DbDep,
    settings: SettingsDep,
) -> EnrichBatchResult:
    get_profile_or_404(db, profile_id)
    client = get_ai_client(settings)
    items = client.enrich_words(body.spellings)
    return EnrichBatchResult(items=items)


@router.post("/scan", response_model=ScanResult)
async def scan_words_from_image(
    profile_id: int,
    _auth: AuthDep,
    db: DbDep,
    settings: SettingsDep,
    file: UploadFile = File(...),
) -> ScanResult:
    get_profile_or_404(db, profile_id)
    mime = (file.content_type or "").lower()
    if mime not in settings.allowed_image_mimes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 jpeg、png、webp、gif 图片",
        )
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片是空的")
    if len(raw) > settings.max_image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="图片太大了，请控制在 5MB 以内",
        )
    # 仅内存处理：缩放压缩后送 AI，不落盘、不写日志正文
    try:
        data_url = prepare_image_data_url(
            raw,
            mime,
            max_side=settings.max_image_side,
            max_bytes=settings.max_image_bytes,
        )
    except InvalidImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="图片无法读取，请重新拍摄或选择其他图片",
        ) from exc
    client = get_ai_client(settings)
    result = client.scan_image(data_url, mime)
    # 规范化候选拼写
    cleaned = []
    seen: set[str] = set()
    for cand in result.candidates:
        spelling = re.sub(r"[^A-Za-z'\\-]", "", cand.spelling.strip())
        if not spelling:
            continue
        key = spelling.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(cand.model_copy(update={"spelling": spelling}))
    return ScanResult(candidates=cleaned[:20])
