from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from backend.app.auth import (
    SettingsDep,
    access_code_matches,
    clear_session_cookie,
    login_client_key,
    set_session_cookie,
    verify_session_token,
)
from backend.app.schemas import LoginRequest, MessageOut, SessionResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=SessionResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    settings: SettingsDep,
) -> SessionResponse:
    client_key = login_client_key(request)
    throttle = request.app.state.login_throttle
    retry_after = throttle.retry_after(client_key)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"尝试次数较多，请稍后再试（约 {retry_after} 秒）",
            headers={"Retry-After": str(retry_after)},
        )
    if not access_code_matches(body.access_code, settings.family_access_code):
        throttle.record_failure(client_key)
        return SessionResponse(authenticated=False, message="访问码不对，请再试一次")
    throttle.clear(client_key)
    set_session_cookie(response, settings)
    return SessionResponse(authenticated=True, message="登录成功")


@router.post("/logout", response_model=MessageOut)
def logout(response: Response, settings: SettingsDep) -> MessageOut:
    clear_session_cookie(response, settings)
    return MessageOut(message="已退出登录")


@router.get("/session", response_model=SessionResponse)
def get_session(request: Request, settings: SettingsDep) -> SessionResponse:
    token = request.cookies.get(settings.cookie_name)
    if token and verify_session_token(token, settings):
        return SessionResponse(authenticated=True)
    return SessionResponse(authenticated=False, message="尚未登录或登录已失效")
