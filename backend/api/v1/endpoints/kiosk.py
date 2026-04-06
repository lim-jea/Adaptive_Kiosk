from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import verify_credentials
from crud.kiosk import (
    create_kiosk,
    get_kiosk_by_api_key,
    list_kiosks,
)
from schemas.kiosk import (
    KioskCreateRequest,
    KioskCreateResponse,
    KioskListRequest,
    KioskResponse,
)
from schemas.common import PaginatedResponse, make_error

router = APIRouter(prefix="/kiosks", tags=["Kiosk"])


async def get_current_kiosk(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """X-API-Key 헤더로 키오스크를 인증."""
    kiosk = await get_kiosk_by_api_key(db, x_api_key)
    if not kiosk or not kiosk.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=make_error("INVALID_API_KEY", "Invalid or inactive API key"),
        )
    return kiosk


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
