"""前端生产挂载路径的集中常量。

API 始终在 /api/wordnest；页面与静态资源在 FRONTEND_BASE_PATH 下。
本地 Vite 开发用根路径 /，生产构建与 FastAPI 静态托管默认 /projects/wordnest。
"""

from __future__ import annotations

import os

DEFAULT_FRONTEND_BASE_PATH = "/projects/wordnest"


def normalize_frontend_base(path: str | None) -> str:
    raw = (path if path is not None else os.getenv("FRONTEND_BASE_PATH", DEFAULT_FRONTEND_BASE_PATH)).strip()
    if not raw or raw == "/":
        return ""
    return "/" + raw.strip("/")
