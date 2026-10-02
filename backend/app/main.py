from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api import auth, dashboard, libraries, profiles, quiz, words
from backend.app.api import settings as settings_api
from backend.app.auth import LoginThrottle
from backend.app.config import get_settings
from backend.app.database import init_db, ping_db
from backend.app.schemas import HealthOut

API_PREFIX = "/api/wordnest"

router = APIRouter()
router.include_router(auth.router)
router.include_router(profiles.router)
router.include_router(libraries.router)
router.include_router(words.router)
router.include_router(quiz.router)
router.include_router(dashboard.router)
router.include_router(settings_api.router)


@router.get("/healthz", response_model=HealthOut)
def healthz() -> HealthOut:
    try:
        ping_db()
        db_status = "ok"
        status = "ok"
    except Exception:  # noqa: BLE001
        db_status = "error"
        status = "degraded"
    return HealthOut(status=status, database=db_status)


def _mount_frontend(app: FastAPI, dist_dir: Path, base_path: str) -> None:
    """挂载生产前端。base_path 为空表示根路径；默认 /projects/wordnest。"""
    assets = dist_dir / "assets"
    asset_mount = f"{base_path}/assets" if base_path else "/assets"
    if assets.is_dir():
        app.mount(asset_mount, StaticFiles(directory=assets), name="assets")

    index = dist_dir / "index.html"

    def _safe_file(full_path: str) -> Path | None:
        if not full_path or full_path.endswith("/"):
            return None
        candidate = (dist_dir / full_path).resolve()
        try:
            candidate.relative_to(dist_dir.resolve())
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    if base_path:

        @app.get(base_path)
        async def spa_base_root() -> FileResponse:
            return FileResponse(index)

        @app.get(f"{base_path}/{{full_path:path}}")
        async def spa_under_base(full_path: str) -> FileResponse:
            file_path = _safe_file(full_path)
            if file_path is not None:
                return FileResponse(file_path)
            return FileResponse(index)

        @app.get("/")
        async def root_redirect() -> RedirectResponse:
            return RedirectResponse(url=f"{base_path}/", status_code=307)
    else:

        @app.get("/{full_path:path}")
        async def spa_root_fallback(full_path: str) -> FileResponse:
            file_path = _safe_file(full_path)
            if file_path is not None:
                return FileResponse(file_path)
            return FileResponse(index)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        init_db()
        yield

    app = FastAPI(title="词芽 WordNest", version="1.0.0", lifespan=lifespan)
    app.state.login_throttle = LoginThrottle()
    app.include_router(router, prefix=API_PREFIX)

    dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist_dir.is_dir() and (dist_dir / "index.html").is_file():
        _mount_frontend(app, dist_dir, settings.frontend_base_path)

    app.state.settings = settings
    return app


app = create_app()
