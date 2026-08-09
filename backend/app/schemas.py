from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


Rating = Literal["unknown", "familiar", "known"]


class LoginRequest(BaseModel):
    access_code: str = Field(min_length=1)


class SessionResponse(BaseModel):
    authenticated: bool
    message: str | None = None


class ProfileOut(OrmModel):
    id: int
    slug: str
    display_name: str


class LibraryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("词库名称不能为空")
        return cleaned


class LibraryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("词库名称不能为空")
        return cleaned


class LibraryOut(OrmModel):
    id: int
    profile_id: int
    name: str
    is_default: bool
    word_count: int = 0
    due_count: int = 0


class WordProgressOut(OrmModel):
    familiarity: int
    correct_streak: int
    review_count: int
    last_rating: str | None
    last_reviewed_at: datetime | None
    next_review_at: datetime | None


class WordOut(OrmModel):
    id: int
    profile_id: int
    spelling: str
    normalized_spelling: str
    meaning_zh: str
    part_of_speech: str
    ipa: str
    syllables: str
    example_en: str
    example_zh: str
    is_mastered: bool
    library_ids: list[int] = Field(default_factory=list)
    progress: WordProgressOut | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WordCreate(BaseModel):
    spelling: str = Field(min_length=1, max_length=120)
    meaning_zh: str = Field(min_length=1, max_length=255)
    part_of_speech: str = ""
    ipa: str = ""
    syllables: str = ""
    example_en: str = ""
    example_zh: str = ""
    library_ids: list[int] = Field(default_factory=list)
    is_mastered: bool = False

    @field_validator("spelling", "meaning_zh")
    @classmethod
    def strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("不能为空")
        return cleaned


class WordBatchCreate(BaseModel):
    items: list[WordCreate] = Field(min_length=1, max_length=20)


class WordBatchOut(BaseModel):
    items: list[WordOut]


class WordUpdate(BaseModel):
    spelling: str | None = Field(default=None, min_length=1, max_length=120)
    meaning_zh: str | None = Field(default=None, min_length=1, max_length=255)
    part_of_speech: str | None = None
    ipa: str | None = None
    syllables: str | None = None
    example_en: str | None = None
    example_zh: str | None = None
    library_ids: list[int] | None = None
    is_mastered: bool | None = None


class EnrichRequest(BaseModel):
    spelling: str = Field(min_length=1, max_length=120)

    @field_validator("spelling")
    @classmethod
    def strip_spelling(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("请输入英语单词")
        return cleaned


class EnrichResult(BaseModel):
    spelling: str
    meaning_zh: str
    part_of_speech: str = ""
    ipa: str = ""
    syllables: str = ""
    example_en: str = ""
    example_zh: str = ""


class EnrichBatchRequest(BaseModel):
    spellings: list[str] = Field(default_factory=list)

    @field_validator("spellings")
    @classmethod
    def normalize_spellings(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in value:
            spelling = raw.strip()
            if not spelling:
                continue
            key = spelling.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(spelling)
        if not cleaned:
            raise ValueError("请至少输入一个英语单词")
        if len(cleaned) > 20:
            raise ValueError("一次最多补全 20 个单词")
        return cleaned


class EnrichBatchResult(BaseModel):
    items: list[EnrichResult]


class ScanCandidate(BaseModel):
    spelling: str
    meaning_zh: str | None = None


class ScanResult(BaseModel):
    candidates: list[ScanCandidate]


class QuizStartRequest(BaseModel):
    library_ids: list[int] = Field(default_factory=list)
    word_ids: list[int] = Field(default_factory=list, max_length=50)
    count: int = Field(default=10, ge=1, le=50)


class QuizWordOut(BaseModel):
    id: int
    spelling: str
    meaning_zh: str
    ipa: str
    syllables: str
    part_of_speech: str = ""
    example_en: str = ""
    example_zh: str = ""
    options: list[str] = Field(default_factory=list)


class QuizStartResponse(BaseModel):
    words: list[QuizWordOut]
    total: int


class QuizPreviewResponse(BaseModel):
    available_count: int
    challenge_count: int


class QuizRateRequest(BaseModel):
    rating: Rating


class QuizRateResponse(BaseModel):
    word_id: int
    familiarity: int
    correct_streak: int
    review_count: int
    next_review_at: datetime | None
    is_mastered: bool


class WeakWordOut(BaseModel):
    id: int
    spelling: str
    meaning_zh: str
    review_count: int
    unknown_count: int
    last_rating: str


class DashboardOut(BaseModel):
    profile: ProfileOut
    libraries: list[LibraryOut]
    total_words: int
    due_words: int
    mastered_words: int
    reviews_7d: int
    known_reviews_7d: int
    steady_accuracy_7d: int
    active_days_7d: int
    weak_words: list[WeakWordOut]


class MessageOut(BaseModel):
    message: str


class HealthOut(BaseModel):
    status: str
    database: str
