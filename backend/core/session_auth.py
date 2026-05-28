"""세션 토큰 ↔ session_uuid 매칭 검증 헬퍼.

POST /sessions 시 발급된 X-Session-Token 이 요청 대상 session_uuid 와 매칭되는지 확인.
- 경로 기반 엔드포인트(/carts/{session_uuid}, /sessions/{session_uuid}): `Depends(verify_session_token)` 사용
- 본문 기반 엔드포인트(/orders, /face/analyze, /voice/*, /logs/batch, /survey/responses):
  handler 내부에서 `assert_token_matches_session(req.session_uuid, x_session_token)` 호출

VITE_KIOSK_API_KEY 가 클라이언트 번들에 노출되더라도, 공격자가 임의 session_uuid 로 다른 사용자의
카트/세션을 조작할 수 없도록 막는 것이 목적이다.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, status

from core.session_token import session_token_store


def assert_token_matches_session(session_uuid: str, x_session_token: Optional[str]) -> None:
    """주어진 session_uuid 와 X-Session-Token 의 매칭을 강제.

    매칭 실패 시 401/403 발생. 매칭 성공 시 반환.
    """
    if not x_session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing session token",
        )
    record = session_token_store.validate(x_session_token)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )
    if record.session_uuid != session_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session token does not match the target session",
        )


async def verify_session_token(
    session_uuid: str,
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
) -> None:
    """FastAPI Dependency.

    경로 파라미터 `session_uuid` 와 헤더 `X-Session-Token` 의 매칭을 검증한다.
    사용 예시:
        @router.get("/{session_uuid}", dependencies=[Depends(verify_session_token)])
    """
    assert_token_matches_session(session_uuid, x_session_token)


async def require_valid_session_token(
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
) -> None:
    """FastAPI Dependency — body/path 의 session_uuid 가 없는 엔드포인트용.

    유효한 X-Session-Token 만 강제. 특정 세션 매칭은 검증하지 않으므로,
    어떤 유효 세션이든 호출 가능. /voice/tts 처럼 텍스트만 받지만 비싼 외부 API 인 경우에 적합.
    rate limit 의 make_debounce 는 토큰의 바인드된 session_uuid 를 사용해 추가 제한을 건다.
    """
    if not x_session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing session token",
        )
    record = session_token_store.validate(x_session_token)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )
