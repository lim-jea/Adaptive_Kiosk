"""관리자 인증 — HttpOnly 쿠키 기반 세션.

XSS 시 sessionStorage 의 관리자 API 키가 탈취되던 문제(2-6) 대응.
프런트엔드는 로그인 폼으로 자격증명을 POST → 서버가 단기 토큰을 발급해 HttpOnly 쿠키로 설정.
이후 관리자 API 호출은 쿠키가 자동 첨부되어 인증되며, 자바스크립트는 토큰 값을 읽을 수 없다.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from pydantic import BaseModel, Field

from core.admin_session import COOKIE_NAME, admin_session_store
from core.config import settings

router = APIRouter(prefix="/admin", tags=["Admin Auth"])


class AdminLoginRequest(BaseModel):
    username: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, max_length=200)
    api_key: str | None = Field(default=None, max_length=200)


class AdminLoginResponse(BaseModel):
    ok: bool
    expires_in: int


def _verify_admin_credentials(req: AdminLoginRequest) -> bool:
    if req.api_key and settings.ADMIN_API_KEY:
        if secrets.compare_digest(req.api_key, settings.ADMIN_API_KEY):
            return True
    if req.username and req.password and settings.KIOSK_USERNAME and settings.KIOSK_PASSWORD:
        ok_user = secrets.compare_digest(req.username, settings.KIOSK_USERNAME)
        ok_pass = secrets.compare_digest(req.password, settings.KIOSK_PASSWORD)
        if ok_user and ok_pass:
            return True
    return False


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(req: AdminLoginRequest, response: Response):
    """관리자 로그인. 성공 시 HttpOnly 쿠키 설정 (30분 TTL).

    요청 본문:
      - { "api_key": "..." }                          # ADMIN_API_KEY 일치
      - { "username": "...", "password": "..." }       # KIOSK_USERNAME/PASSWORD 일치
    """
    if not _verify_admin_credentials(req):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")

    token, ttl = admin_session_store.issue()
    # SameSite=Strict: 외부 사이트가 자동 첨부하지 못해 CSRF 방어.
    # Secure 는 HTTPS 환경에서만 전송. 로컬 dev 는 SECURE_COOKIES=false 로 비활성.
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=ttl,
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="strict",
        path="/",
    )
    return AdminLoginResponse(ok=True, expires_in=ttl)


@router.post("/logout")
async def admin_logout(
    response: Response,
    admin_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
):
    """관리자 로그아웃. 쿠키 폐기 + 서버 측 토큰 무효화."""
    if admin_session:
        admin_session_store.revoke(admin_session)
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
async def admin_me(
    admin_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
):
    """현재 관리자 세션 유효성 확인. 프런트엔드의 로그인 상태 복구용."""
    if not admin_session or not admin_session_store.validate(admin_session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return {"ok": True}
