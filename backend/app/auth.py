from __future__ import annotations

import secrets
import time
from collections import deque
from ipaddress import ip_address
from math import ceil
from threading import Lock
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from backend.app.config import Settings, get_settings
from backend.app.database import get_db

SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 60


class LoginThrottle:
    """单实例访问码失败节流器；生产容器当前为单进程。"""

    def __init__(
        self,
        max_attempts: int = MAX_FAILED_LOGIN_ATTEMPTS,
        window_seconds: int = LOGIN_ATTEMPT_WINDOW_SECONDS,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        failures = self._failures.setdefault(key, deque())
        cutoff = now - self.window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if not failures:
            self._failures.pop(key, None)
            return deque()
        return failures

    def retry_after(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            failures = self._prune(key, now)
            if len(failures) < self.max_attempts:
                return 0
            return max(1, ceil(failures[0] + self.window_seconds - now))

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            failures = self._prune(key, now)
            if not failures:
                failures = self._failures.setdefault(key, deque())
            failures.append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


def login_client_key(request: Request) -> str:
    peer_host = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-real-ip")
    if forwarded and _is_private_proxy(peer_host):
        return forwarded.strip()
    return peer_host


def _is_private_proxy(host: str) -> bool:
    try:
        address = ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt="wordnest-auth")


def create_session_token(settings: Settings) -> str:
    return _serializer(settings).dumps({"auth": True})


def verify_session_token(token: str, settings: Settings) -> bool:
    try:
        data = _serializer(settings).loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return bool(data.get("auth"))


def access_code_matches(provided: str, expected: str) -> bool:
    return secrets.compare_digest(provided.strip(), expected.strip())


def set_session_cookie(response: Response, settings: Settings) -> None:
    token = create_session_token(settings)
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=SESSION_MAX_AGE,
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        samesite="lax",
        secure=settings.is_production,
        httponly=True,
    )


def require_auth(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    token = request.cookies.get(settings.cookie_name)
    if not token or not verify_session_token(token, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新输入家庭访问码",
        )


AuthDep = Annotated[None, Depends(require_auth)]
DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def optional_session_cookie(
    settings: SettingsDep,
    wordnest_session: Annotated[str | None, Cookie(alias="wordnest_session")] = None,
) -> str | None:
    return wordnest_session
