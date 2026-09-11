from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    libraries: Mapped[list[Library]] = relationship(back_populates="profile")
    words: Mapped[list[Word]] = relationship(back_populates="profile")


class Library(Base):
    __tablename__ = "libraries"
    __table_args__ = (UniqueConstraint("profile_id", "name", name="uq_library_profile_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    profile: Mapped[Profile] = relationship(back_populates="libraries")
    library_words: Mapped[list[LibraryWord]] = relationship(
        back_populates="library", cascade="all, delete-orphan"
    )


class Word(Base):
    __tablename__ = "words"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "normalized_spelling", name="uq_word_profile_normalized"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    normalized_spelling: Mapped[str] = mapped_column(String(120), nullable=False)
    spelling: Mapped[str] = mapped_column(String(120), nullable=False)
    meaning_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    part_of_speech: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    ipa: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    syllables: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    example_en: Mapped[str] = mapped_column(Text, default="", nullable=False)
    example_zh: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_mastered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    profile: Mapped[Profile] = relationship(back_populates="words")
    library_words: Mapped[list[LibraryWord]] = relationship(
        back_populates="word", cascade="all, delete-orphan"
    )
    progress: Mapped[WordProgress | None] = relationship(
        back_populates="word", uselist=False, cascade="all, delete-orphan"
    )


class LibraryWord(Base):
    __tablename__ = "library_words"

    library_id: Mapped[int] = mapped_column(
        ForeignKey("libraries.id", ondelete="CASCADE"), primary_key=True
    )
    word_id: Mapped[int] = mapped_column(
        ForeignKey("words.id", ondelete="CASCADE"), primary_key=True
    )

    library: Mapped[Library] = relationship(back_populates="library_words")
    word: Mapped[Word] = relationship(back_populates="library_words")


class WordProgress(Base):
    __tablename__ = "word_progress"
    __table_args__ = (
        UniqueConstraint("profile_id", "word_id", name="uq_progress_profile_word"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    word_id: Mapped[int] = mapped_column(
        ForeignKey("words.id", ondelete="CASCADE"), nullable=False, index=True
    )
    familiarity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_rating: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    word: Mapped[Word] = relationship(back_populates="progress")


class ReviewEvent(Base):
    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    word_id: Mapped[int] = mapped_column(
        ForeignKey("words.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
