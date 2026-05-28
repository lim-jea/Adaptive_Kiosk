from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import verify_credentials
from core.session_token import session_token_store
from crud.kiosk import (
    create_kiosk,
    get_kiosk_by_api_key,
    get_kiosk_by_id,
    list_kiosks,
    update_kiosk,
)
from schemas import (
    KioskCreateRequest,
    KioskCreateResponse,
    KioskListRequest,
    KioskResponse,
    KioskUpdateRequest,
)
from schemas import PaginatedResponse, make_error

router = APIRouter(prefix="/kiosks", tags=["Kiosk"])


async def get_current_kiosk(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
    db: AsyncSession = Depends(get_db),
):
    """X-API-Key 헤더(영구 키, /sessions POST 전용) 또는 X-Session-Token(단기 토큰, 세션 생성 후) 으로 키오스크를 인증.

    프런트엔드는 다음 흐름을 권장:
      1) 첫 요청(/sessions POST): X-API-Key 헤더로 키오스크 인증 → access_token 발급받음
      2) 이후 요청: X-Session-Token 헤더 사용 (X-API-Key 는 클라이언트 번들 노출 회피)
    """
    if x_session_token:
        record = session_token_store.validate(x_session_token)
        if record:
            kiosk = await get_kiosk_by_id(db, record.kiosk_id)
            if kiosk and kiosk.is_active:
                return kiosk
    if x_api_key:
        kiosk = await get_kiosk_by_api_key(db, x_api_key)
        if kiosk and kiosk.is_active:
            return kiosk
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=make_error("INVALID_API_KEY", "Invalid or inactive credentials"),
    )


@router.post(
    "",
    response_model=KioskCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_kiosk_endpoint(
    req: KioskCreateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """키오스크 생성 + API 키 발급. 관리자 인증 필요."""
    kiosk = await create_kiosk(db, name=req.name, location=req.location)
    return KioskCreateResponse(
        id=kiosk.id,
        name=kiosk.name,
        location=kiosk.location,
        is_active=kiosk.is_active,
        registered_at=kiosk.registered_at,
        last_seen_at=kiosk.last_seen_at,
        api_key=kiosk.api_key,
    )


@router.get("", response_model=PaginatedResponse[KioskResponse])
async def list_kiosks_endpoint(
    req: KioskListRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """키오스크 목록. 관리자 인증 필요."""
    items, total = await list_kiosks(
        db, is_active=req.is_active, skip=req.skip, limit=req.limit
    )
    return PaginatedResponse(items=items, total=total, skip=req.skip, limit=req.limit)


@router.get("/me", response_model=KioskResponse)
async def get_my_kiosk(kiosk=Depends(get_current_kiosk)):
    """현재 X-API-Key로 인증된 키오스크 정보."""
    return kiosk


@router.patch("/{kiosk_id}", response_model=KioskResponse)
async def update_kiosk_endpoint(
    kiosk_id: int,
    req: KioskUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """키오스크 부분 수정. 관리자 인증 필요."""
    updates = req.model_dump(exclude_unset=True)
    kiosk = await update_kiosk(db, kiosk_id, updates)
    if not kiosk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("KIOSK_NOT_FOUND", "Kiosk not found", kiosk_id=kiosk_id),
        )
    return kiosk
