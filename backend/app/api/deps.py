from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.models import Library, LibraryWord, Profile, Word, WordProgress
from backend.app.schemas import LibraryOut, WordOut, WordProgressOut


def get_profile_or_404(db: Session, profile_id: int) -> Profile:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到这个孩子")
    return profile


def get_library_for_profile(db: Session, profile_id: int, library_id: int) -> Library:
    library = db.get(Library, library_id)
    if library is None or library.profile_id != profile_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到这个词库")
    return library


def get_word_for_profile(db: Session, profile_id: int, word_id: int) -> Word:
    word = db.scalar(
        select(Word)
        .where(Word.id == word_id, Word.profile_id == profile_id)
        .options(selectinload(Word.library_words), selectinload(Word.progress))
    )
    if word is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到这个单词")
    return word


def normalize_spelling(spelling: str) -> str:
    return spelling.strip().lower()


def library_to_out(db: Session, library: Library) -> LibraryOut:
    word_count = db.scalar(
        select(func.count())
        .select_from(LibraryWord)
        .where(LibraryWord.library_id == library.id)
    ) or 0
    now = datetime.now(timezone.utc)
    due_count = db.scalar(
        select(func.count())
        .select_from(LibraryWord)
        .join(Word, Word.id == LibraryWord.word_id)
        .outerjoin(WordProgress, WordProgress.word_id == Word.id)
        .where(
            LibraryWord.library_id == library.id,
            Word.is_mastered.is_(False),
            (WordProgress.next_review_at.is_(None))
            | (WordProgress.next_review_at <= now),
        )
    ) or 0
    return LibraryOut(
        id=library.id,
        profile_id=library.profile_id,
        name=library.name,
        is_default=library.is_default,
        word_count=int(word_count),
        due_count=int(due_count),
    )


def word_to_out(word: Word) -> WordOut:
    progress_out = None
    if word.progress is not None:
        progress_out = WordProgressOut.model_validate(word.progress)
    return WordOut(
        id=word.id,
        profile_id=word.profile_id,
        spelling=word.spelling,
        normalized_spelling=word.normalized_spelling,
        meaning_zh=word.meaning_zh,
        part_of_speech=word.part_of_speech,
        ipa=word.ipa,
        syllables=word.syllables,
        example_en=word.example_en,
        example_zh=word.example_zh,
        is_mastered=word.is_mastered,
        library_ids=[lw.library_id for lw in word.library_words],
        progress=progress_out,
        created_at=word.created_at,
        updated_at=word.updated_at,
    )


def ensure_libraries_belong(
    db: Session, profile_id: int, library_ids: list[int]
) -> list[Library]:
    if not library_ids:
        default = db.scalar(
            select(Library).where(
                Library.profile_id == profile_id, Library.is_default.is_(True)
            )
        )
        if default is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="还没有可用词库"
            )
        return [default]
    libraries = list(
        db.scalars(
            select(Library).where(
                Library.profile_id == profile_id, Library.id.in_(library_ids)
            )
        ).all()
    )
    if len(libraries) != len(set(library_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="有些词库不属于当前孩子",
        )
    return libraries


def sync_word_libraries(db: Session, word: Word, libraries: list[Library]) -> None:
    existing = {lw.library_id: lw for lw in word.library_words}
    target_ids = {lib.id for lib in libraries}
    for lib_id, link in list(existing.items()):
        if lib_id not in target_ids:
            db.delete(link)
    for lib in libraries:
        if lib.id not in existing:
            db.add(LibraryWord(library_id=lib.id, word_id=word.id))
