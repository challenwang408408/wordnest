from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import func, select

from backend.app.api.deps import get_profile_or_404, library_to_out
from backend.app.auth import AuthDep, DbDep, SettingsDep
from backend.app.models import Library, ReviewEvent, Word, WordProgress
from backend.app.schemas import DashboardOut, ProfileOut, WeakWordOut

router = APIRouter(prefix="/profiles/{profile_id}", tags=["dashboard"])


def local_review_date(reviewed_at: datetime, family_tz: ZoneInfo) -> date:
    if reviewed_at.tzinfo is None:
        reviewed_at = reviewed_at.replace(tzinfo=timezone.utc)
    return reviewed_at.astimezone(family_tz).date()


def family_day_window(
    now: datetime,
    family_tz: ZoneInfo,
    *,
    days: int,
) -> tuple[datetime, datetime]:
    """返回包含今天在内的 N 个家庭自然日，对应的 UTC 左闭右开区间。"""
    local_today = now.astimezone(family_tz).date()
    start_day = local_today - timedelta(days=days - 1)
    end_day = local_today + timedelta(days=1)
    start_local = datetime.combine(start_day, time.min, tzinfo=family_tz)
    end_local = datetime.combine(end_day, time.min, tzinfo=family_tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    profile_id: int,
    _auth: AuthDep,
    db: DbDep,
    settings: SettingsDep,
) -> DashboardOut:
    profile = get_profile_or_404(db, profile_id)
    libraries = list(
        db.scalars(
            select(Library).where(Library.profile_id == profile_id).order_by(Library.id)
        ).all()
    )
    total_words = db.scalar(
        select(func.count()).select_from(Word).where(Word.profile_id == profile_id)
    ) or 0
    mastered_words = db.scalar(
        select(func.count())
        .select_from(Word)
        .where(Word.profile_id == profile_id, Word.is_mastered.is_(True))
    ) or 0
    now = datetime.now(timezone.utc)
    due_words = db.scalar(
        select(func.count())
        .select_from(Word)
        .outerjoin(WordProgress, WordProgress.word_id == Word.id)
        .where(
            Word.profile_id == profile_id,
            Word.is_mastered.is_(False),
            (WordProgress.next_review_at.is_(None))
            | (WordProgress.next_review_at <= now),
        )
    ) or 0
    family_tz = ZoneInfo(settings.family_timezone)
    window_start, window_end = family_day_window(now, family_tz, days=7)
    events = list(
        db.scalars(
            select(ReviewEvent)
            .where(
                ReviewEvent.profile_id == profile_id,
                ReviewEvent.reviewed_at >= window_start,
                ReviewEvent.reviewed_at < window_end,
            )
            .order_by(ReviewEvent.reviewed_at.desc(), ReviewEvent.id.desc())
        ).all()
    )
    reviews_7d = len(events)
    known_reviews_7d = sum(event.rating == "known" for event in events)
    active_days_7d = len(
        {local_review_date(event.reviewed_at, family_tz) for event in events}
    )

    weak_by_word: dict[int, dict[str, int | str]] = {}
    for event in events:
        item = weak_by_word.setdefault(
            event.word_id,
            {"review_count": 0, "unknown_count": 0, "last_rating": event.rating},
        )
        item["review_count"] = int(item["review_count"]) + 1
        if event.rating == "unknown":
            item["unknown_count"] = int(item["unknown_count"]) + 1

    weak_ids = [
        word_id
        for word_id, item in weak_by_word.items()
        if int(item["unknown_count"]) > 0
    ]
    word_map = {
        word.id: word
        for word in db.scalars(
            select(Word).where(Word.profile_id == profile_id, Word.id.in_(weak_ids))
        ).all()
    } if weak_ids else {}
    ranked_weak_ids = sorted(
        weak_ids,
        key=lambda word_id: (
            str(weak_by_word[word_id]["last_rating"]) == "unknown",
            str(weak_by_word[word_id]["last_rating"]) == "familiar",
            int(weak_by_word[word_id]["unknown_count"])
            / max(1, int(weak_by_word[word_id]["review_count"])),
            int(weak_by_word[word_id]["unknown_count"]),
        ),
        reverse=True,
    )[:5]
    weak_words = [
        WeakWordOut(
            id=word_id,
            spelling=word_map[word_id].spelling,
            meaning_zh=word_map[word_id].meaning_zh,
            review_count=int(weak_by_word[word_id]["review_count"]),
            unknown_count=int(weak_by_word[word_id]["unknown_count"]),
            last_rating=str(weak_by_word[word_id]["last_rating"]),
        )
        for word_id in ranked_weak_ids
        if word_id in word_map
    ]
    return DashboardOut(
        profile=ProfileOut.model_validate(profile),
        libraries=[library_to_out(db, lib) for lib in libraries],
        total_words=int(total_words),
        due_words=int(due_words),
        mastered_words=int(mastered_words),
        reviews_7d=reviews_7d,
        known_reviews_7d=known_reviews_7d,
        steady_accuracy_7d=(
            round(known_reviews_7d / reviews_7d * 100) if reviews_7d else 0
        ),
        active_days_7d=active_days_7d,
        weak_words=weak_words,
    )
