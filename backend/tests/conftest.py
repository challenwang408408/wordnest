from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# 强制覆盖，避免开发 .env / 残留 shell 环境污染测试
os.environ["FAMILY_ACCESS_CODE"] = "test-family-code"
os.environ["SESSION_SECRET"] = "test-session-secret-32chars!!"
os.environ["APP_ENV"] = "development"
os.environ["AI_BUILDER_TOKEN"] = ""
os.environ["FRONTEND_BASE_PATH"] = "/projects/wordnest"

from backend.app import database as db_module
from backend.app.config import get_settings
from backend.app.main import create_app
from backend.app.seed import seed_profiles
from backend.app.services.ai_builder import MockAIBuilderClient, set_ai_client

get_settings.cache_clear()


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def client(db_path: Path) -> Generator[TestClient, None, None]:
    os.environ["FAMILY_ACCESS_CODE"] = "test-family-code"
    os.environ["SESSION_SECRET"] = "test-session-secret-32chars!!"
    get_settings.cache_clear()
    url = f"sqlite:///{db_path}"
    db_module.reset_engine(url)
    db_module.Base.metadata.create_all(bind=db_module.engine)
    with db_module.SessionLocal() as db:
        seed_profiles(db)
        db.commit()

    set_ai_client(MockAIBuilderClient())
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    set_ai_client(None)
    get_settings.cache_clear()


@pytest.fixture()
def auth_client(client: TestClient) -> TestClient:
    resp = client.post(
        "/api/wordnest/auth/login", json={"access_code": "test-family-code"}
    )
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is True
    return client


@pytest.fixture()
def profiles(auth_client: TestClient) -> dict[str, int]:
    resp = auth_client.get("/api/wordnest/profiles")
    assert resp.status_code == 200
    data = resp.json()
    return {p["slug"]: p["id"] for p in data}
