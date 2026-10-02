from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.deps import get_profile_or_404
from backend.app.auth import AuthDep, DbDep
from backend.app.models import ProfileSettings
from backend.app.schemas import ProfileSettingsOut, ProfileSettingsUpdate

router = APIRouter(prefix="/profiles/{profile_id}", tags=["settings"])


@router.patch("/settings", response_model=ProfileSettingsOut)
def update_settings(
    profile_id: int,
    body: ProfileSettingsUpdate,
    _auth: AuthDep,
    db: DbDep,
) -> ProfileSettingsOut:
    get_profile_or_404(db, profile_id)
    settings = db.get(ProfileSettings, profile_id)
    if settings is None:
        settings = ProfileSettings(profile_id=profile_id)
        db.add(settings)
    settings.daily_quiz_count = body.daily_quiz_count
    db.commit()
    return ProfileSettingsOut(daily_quiz_count=settings.daily_quiz_count)
