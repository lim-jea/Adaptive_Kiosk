from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.rate_limit import make_ip_rate_limit
from core.security import verify_credentials
from core.session_auth import verify_session_token
from core.session_token import session_token_store
from crud.session import create_session, get_session_by_uuid, list_sessions, update_session
from schemas import (
    SessionCreateResponse,
    SessionListRequest,
    SessionUpdateRequest,
    SessionResponse,
    PaginatedResponse,
    make_error,
)
from model import Kiosk
from api.v1.endpoints.kiosk import get_current_kiosk
from services.cart_service import ensure_cart_for_session

router = APIRouter(prefix="/sessions", tags=["Session"])


@router.post(
    "",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    # 토큰 발급 전 엔드포인트라 세션 디바운스 적용 불가 → 노출된 API key 봇 남용을 IP 분당 캡으로 차단.
    dependencies=[Depends(make_ip_rate_limit(max_per_minute=20))],
)
async def create_session_endpoint(
    kiosk: Kiosk = Depends(get_current_kiosk),
    db: AsyncSession = Depends(get_db),
):
    """세션 생성. X-API-Key 헤더로 키오스크 인증.
    응답에 단기 access_token(기본 30분) 포함 — 프런트엔드는 이후 호출에 X-Session-Token 헤더 사용 권장.
    """
    session = await create_session(db, kiosk_id=kiosk.id)
    await ensure_cart_for_session(db, session.id)
    token, ttl = session_token_store.issue(session.session_uuid, kiosk.id)
    return SessionCreateResponse(
        session_uuid=session.session_uuid,
        kiosk_id=session.kiosk_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        end_reason=session.end_reason,
        is_simple_mode=session.is_simple_mode,
        estimated_age_group=session.estimated_age_group,
        estimated_gender=session.estimated_gender,
        help_triggered=session.help_triggered,
        status=session.status,
        access_token=token,
        expires_in=ttl,
    )


@router.get("", response_model=PaginatedResponse[SessionResponse])
async def list_sessions_endpoint(
    req: SessionListRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """세션 목록. 관리자 인증 필요."""
    items, total = await list_sessions(
        db, status=req.status, kiosk_id=req.kiosk_id, skip=req.skip, limit=req.limit
    )
    return PaginatedResponse(items=items, total=total, skip=req.skip, limit=req.limit)


@router.get(
    "/{session_uuid}",
    response_model=SessionResponse,
    dependencies=[Depends(verify_session_token)],
)
async def read_session(session_uuid: str, db: AsyncSession = Depends(get_db)):
    """세션 단건 조회. X-Session-Token 이 session_uuid 와 매칭해야 한다."""
    session = await get_session_by_uuid(db, session_uuid)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("SESSION_NOT_FOUND", "Session not found", session_uuid=session_uuid),
        )
    return session


@router.patch(
    "/{session_uuid}",
    response_model=SessionResponse,
    dependencies=[Depends(verify_session_token)],
)
async def update_session_endpoint(
    session_uuid: str,
    req: SessionUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """세션 상태 갱신.
    종료: { "status": "ended", "end_reason": "completed" }
    간편모드 전환: { "is_simple_mode": true, "estimated_age_group": "60대" }
    """
    updates = req.model_dump(exclude_unset=True, exclude_none=True)
    # enum → str 변환
    if "status" in updates and hasattr(updates["status"], "value"):
        updates["status"] = updates["status"].value
    if "end_reason" in updates and hasattr(updates["end_reason"], "value"):
        updates["end_reason"] = updates["end_reason"].value

    session = await update_session(db, session_uuid, updates)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("SESSION_NOT_FOUND", "Session not found", session_uuid=session_uuid),
        )
    return session
