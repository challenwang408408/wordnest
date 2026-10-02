from __future__ import annotations

import random
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.models import LibraryWord, ReviewEvent, Word, WordProgress
from backend.app.schemas import Rating

RATING_DELTAS: dict[Rating, tuple[int, int, timedelta | None]] = {
    # familiarity delta, streak delta or reset, next_review delay
    "unknown": (-2, 0, timedelta(hours=4)),
    "familiar": (1, 0, timedelta(days=1)),
    "known": (2, 1, timedelta(days=3)),
}

OPTION_COUNT = 4

# 新词库只有一两个词时，干扰项不够，用小学常见义兜底，保证每题都是四选一
FALLBACK_DISTRACTORS: tuple[str, ...] = (
    "苹果",
    "书",
    "小狗",
    "学校",
    "朋友",
    "水",
    "妈妈",
    "桌子",
    "开心的",
    "红色的",
    "大的",
    "跑",
    "唱歌",
    "看见",
    "早上",
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def select_quiz_words(
    db: Session,
    *,
    profile_id: int,
    library_ids: list[int],
    word_ids: list[int],
    count: int,
    min_wrong_count: int = 0,
) -> list[Word]:
    stmt = _eligible_words_stmt(
        profile_id=profile_id,
        library_ids=library_ids,
        word_ids=word_ids,
        min_wrong_count=min_wrong_count,
    ).options(selectinload(Word.progress), selectinload(Word.library_words))
    words = list(db.scalars(stmt).unique().all())
    if not words:
        return []

    now = utcnow()

    def score(word: Word) -> float:
        progress = word.progress
        familiarity = progress.familiarity if progress else 0
        last = progress.last_reviewed_at if progress else None
        next_at = progress.next_review_at if progress else None
        due_bonus = 0.0
        if next_at is None or _as_aware(next_at) <= now:
            due_bonus = 40.0
        age_bonus = 0.0
        if last is None:
            age_bonus = 20.0
        else:
            days = max(0.0, (now - _as_aware(last)).total_seconds() / 86400)
            age_bonus = min(20.0, days * 2)
        low_fam = max(0.0, 10 - familiarity) * 3
        noise = random.random() * 8
        return due_bonus + age_bonus + low_fam + noise

    ranked = sorted(words, key=score, reverse=True)
    return ranked[: min(count, len(ranked))]


def count_available_quiz_words(
    db: Session,
    *,
    profile_id: int,
    library_ids: list[int],
    word_ids: list[int],
    min_wrong_count: int = 0,
) -> int:
    eligible = _eligible_words_stmt(
        profile_id=profile_id,
        library_ids=library_ids,
        word_ids=word_ids,
        min_wrong_count=min_wrong_count,
    ).with_only_columns(Word.id)
    return int(db.scalar(select(func.count()).select_from(eligible.subquery())) or 0)


def _eligible_words_stmt(
    *,
    profile_id: int,
    library_ids: list[int],
    word_ids: list[int],
    min_wrong_count: int = 0,
):
    stmt = (
        select(Word)
        .where(Word.profile_id == profile_id, Word.is_mastered.is_(False))
    )
    if library_ids:
        stmt = (
            stmt.join(LibraryWord, LibraryWord.word_id == Word.id)
            .where(LibraryWord.library_id.in_(library_ids))
            .distinct()
        )
    if word_ids:
        stmt = stmt.where(Word.id.in_(word_ids))
    if min_wrong_count > 0:
        frequent_ids = (
            select(ReviewEvent.word_id)
            .where(ReviewEvent.profile_id == profile_id, ReviewEvent.rating == "unknown")
            .group_by(ReviewEvent.word_id)
            .having(func.count() >= min_wrong_count)
        )
        stmt = stmt.where(Word.id.in_(frequent_ids))
    return stmt


def collect_meaning_pool(db: Session, *, profile_id: int) -> list[str]:
    """当前孩子已有的全部中文释义，用来当选择题干扰项。"""
    meanings = db.scalars(
        select(Word.meaning_zh).where(Word.profile_id == profile_id)
    ).all()
    seen: set[str] = set()
    pool: list[str] = []
    for meaning in meanings:
        cleaned = (meaning or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        pool.append(cleaned)
    return pool


def build_options(
    correct_meaning: str,
    pool: Sequence[str],
    *,
    count: int = OPTION_COUNT,
    rng: random.Random | None = None,
) -> list[str]:
    """生成打乱后的四选一选项，保证含唯一正确答案。"""
    picker = rng or random
    answer = (correct_meaning or "").strip()
    if not answer:
        answer = "不确定"

    candidates = [m for m in dict.fromkeys(pool) if m.strip() and m.strip() != answer]
    picker.shuffle(candidates)
    distractors = candidates[: count - 1]

    if len(distractors) < count - 1:
        extra = [m for m in FALLBACK_DISTRACTORS if m != answer and m not in distractors]
        picker.shuffle(extra)
        distractors.extend(extra[: count - 1 - len(distractors)])

    options = [answer, *distractors]
    picker.shuffle(options)
    return options


def apply_rating(
    db: Session,
    *,
    profile_id: int,
    word: Word,
    rating: Rating,
) -> WordProgress:
    progress = word.progress
    if progress is None:
        progress = WordProgress(profile_id=profile_id, word_id=word.id)
        db.add(progress)
        word.progress = progress

    fam_delta, streak_mode, delay = RATING_DELTAS[rating]
    progress.familiarity = max(0, min(10, progress.familiarity + fam_delta))
    if rating == "unknown":
        progress.correct_streak = 0
    elif rating == "known":
        progress.correct_streak += streak_mode
    else:
        # familiar: keep streak but don't grow mastery path aggressively
        progress.correct_streak = max(0, progress.correct_streak)

    progress.review_count += 1
    progress.last_rating = rating
    now = utcnow()
    progress.last_reviewed_at = now
    progress.next_review_at = now + delay if delay else now

    if rating == "known" and progress.correct_streak >= 3 and progress.familiarity >= 8:
        word.is_mastered = True

    return progress


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
