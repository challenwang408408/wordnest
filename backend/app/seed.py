from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Library, Profile

DEFAULT_PROFILES = (
    ("brother", "哥哥"),
    ("sister", "妹妹"),
)
DEFAULT_LIBRARY_NAME = "日常阅读"


def seed_profiles(db: Session) -> None:
    """幂等创建哥哥、妹妹及各自默认词库。"""
    for slug, display_name in DEFAULT_PROFILES:
        profile = db.scalar(select(Profile).where(Profile.slug == slug))
        if profile is None:
            profile = Profile(slug=slug, display_name=display_name)
            db.add(profile)
            db.flush()
        default_lib = db.scalar(
            select(Library).where(
                Library.profile_id == profile.id,
                Library.is_default.is_(True),
            )
        )
        if default_lib is None:
            db.add(
                Library(
                    profile_id=profile.id,
                    name=DEFAULT_LIBRARY_NAME,
                    is_default=True,
                )
            )
