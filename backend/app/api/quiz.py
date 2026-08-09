from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.deps import ensure_libraries_belong, get_profile_or_404, get_word_for_profile
from backend.app.auth import AuthDep, DbDep
from backend.app.models import ReviewEvent
from backend.app.schemas import (
    QuizRateRequest,
    QuizRateResponse,
    QuizPreviewResponse,
    QuizStartRequest,
    QuizStartResponse,
    QuizWordOut,
)
from backend.app.services.quiz import (
    apply_rating,
    build_options,
    collect_meaning_pool,
    count_available_quiz_words,
    select_quiz_words,
)

router = APIRouter(prefix="/profiles/{profile_id}/quiz", tags=["quiz"])


@router.post("/preview", response_model=QuizPreviewResponse)
def preview_quiz(
    profile_id: int,
    body: QuizStartRequest,
    _auth: AuthDep,
    db: DbDep,
) -> QuizPreviewResponse:
    get_profile_or_404(db, profile_id)
    if body.library_ids:
        ensure_libraries_belong(db, profile_id, body.library_ids)
    available_count = count_available_quiz_words(
        db,
        profile_id=profile_id,
        library_ids=body.library_ids,
        word_ids=body.word_ids,
    )
    return QuizPreviewResponse(
        available_count=available_count,
        challenge_count=min(body.count, available_count),
    )


@router.post("/start", response_model=QuizStartResponse)
def start_quiz(
    profile_id: int,
    body: QuizStartRequest,
    _auth: AuthDep,
    db: DbDep,
) -> QuizStartResponse:
    get_profile_or_404(db, profile_id)
    library_ids = body.library_ids
    if library_ids:
        ensure_libraries_belong(db, profile_id, library_ids)
    words = select_quiz_words(
        db,
        profile_id=profile_id,
        library_ids=library_ids,
        word_ids=body.word_ids,
        count=body.count,
    )
    meaning_pool = collect_meaning_pool(db, profile_id=profile_id)
    payload = [
        QuizWordOut(
            id=w.id,
            spelling=w.spelling,
            meaning_zh=w.meaning_zh,
            ipa=w.ipa,
            syllables=w.syllables,
            part_of_speech=w.part_of_speech,
            example_en=w.example_en,
            example_zh=w.example_zh,
            options=build_options(w.meaning_zh, meaning_pool),
        )
        for w in words
    ]
    return QuizStartResponse(words=payload, total=len(payload))


@router.post("/{word_id}/rate", response_model=QuizRateResponse)
def rate_word(
    profile_id: int,
    word_id: int,
    body: QuizRateRequest,
    _auth: AuthDep,
    db: DbDep,
) -> QuizRateResponse:
    word = get_word_for_profile(db, profile_id, word_id)
    progress = apply_rating(db, profile_id=profile_id, word=word, rating=body.rating)
    db.add(
        ReviewEvent(
            profile_id=profile_id,
            word_id=word_id,
            rating=body.rating,
        )
    )
    db.commit()
    db.refresh(progress)
    db.refresh(word)
    return QuizRateResponse(
        word_id=word.id,
        familiarity=progress.familiarity,
        correct_streak=progress.correct_streak,
        review_count=progress.review_count,
        next_review_at=progress.next_review_at,
        is_mastered=word.is_mastered,
    )
