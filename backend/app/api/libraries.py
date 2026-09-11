from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.app.api.deps import (
    get_library_for_profile,
    get_profile_or_404,
    library_to_out,
)
from backend.app.auth import AuthDep, DbDep
from backend.app.models import Library, LibraryWord
from backend.app.schemas import LibraryCreate, LibraryOut, LibraryUpdate, MessageOut

router = APIRouter(prefix="/profiles/{profile_id}/libraries", tags=["libraries"])


@router.get("", response_model=list[LibraryOut])
def list_libraries(profile_id: int, _auth: AuthDep, db: DbDep) -> list[LibraryOut]:
    get_profile_or_404(db, profile_id)
    libraries = list(
        db.scalars(
            select(Library).where(Library.profile_id == profile_id).order_by(Library.id)
        ).all()
    )
    return [library_to_out(db, lib) for lib in libraries]


@router.post("", response_model=LibraryOut, status_code=status.HTTP_201_CREATED)
def create_library(
    profile_id: int,
    body: LibraryCreate,
    _auth: AuthDep,
    db: DbDep,
) -> LibraryOut:
    get_profile_or_404(db, profile_id)
    library = Library(profile_id=profile_id, name=body.name, is_default=False)
    db.add(library)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="这个孩子已经有同名词库了"
        ) from exc
    db.refresh(library)
    return library_to_out(db, library)


@router.patch("/{library_id}", response_model=LibraryOut)
def rename_library(
    profile_id: int,
    library_id: int,
    body: LibraryUpdate,
    _auth: AuthDep,
    db: DbDep,
) -> LibraryOut:
    library = get_library_for_profile(db, profile_id, library_id)
    library.name = body.name
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="这个孩子已经有同名词库了"
        ) from exc
    db.refresh(library)
    return library_to_out(db, library)


@router.delete("/{library_id}", response_model=MessageOut)
def delete_library(
    profile_id: int,
    library_id: int,
    _auth: AuthDep,
    db: DbDep,
    force: bool = Query(default=False),
) -> MessageOut:
    library = get_library_for_profile(db, profile_id, library_id)
    if library.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="默认词库不能删除"
        )
    count = (
        db.scalar(
            select(func.count())
            .select_from(LibraryWord)
            .where(LibraryWord.library_id == library.id)
        )
        or 0
    )
    if count > 0 and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"词库里还有 {count} 个单词，确认删除请带上 force=true"
                "（只解除关联，不会删掉其他词库里的单词）"
            ),
        )
    db.delete(library)
    db.commit()
    return MessageOut(message="词库已删除")
