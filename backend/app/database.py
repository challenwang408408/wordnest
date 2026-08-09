from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(database_url: str):
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(database_url, connect_args=connect_args, future=True)

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


settings = get_settings()
engine = _make_engine(settings.resolved_database_url())
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from backend.app import models  # noqa: F401
    from backend.app.seed import seed_profiles

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_profiles(db)
        db.commit()


def reset_engine(database_url: str) -> None:
    """测试用：切换数据库引擎，并同步 get_db 使用的 SessionLocal。"""
    global engine, SessionLocal
    engine.dispose()
    engine = _make_engine(database_url)
    SessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )


def ensure_parent_dir(sqlite_url: str) -> None:
    if not sqlite_url.startswith("sqlite:///"):
        return
    path = Path(sqlite_url.removeprefix("sqlite:///"))
    if path.parent and str(path.parent) not in {".", ""}:
        path.parent.mkdir(parents=True, exist_ok=True)


def ping_db() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
