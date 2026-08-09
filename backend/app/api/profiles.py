from __future__ import annotations

from fastapi import APIRouter

from backend.app.auth import AuthDep, DbDep
from backend.app.models import Profile
from backend.app.schemas import ProfileOut
from sqlalchemy import select

router = APIRouter(tags=["profiles"])


@router.get("/profiles", response_model=list[ProfileOut])
def list_profiles(_auth: AuthDep, db: DbDep) -> list[Profile]:
    return list(db.scalars(select(Profile).order_by(Profile.id)).all())
