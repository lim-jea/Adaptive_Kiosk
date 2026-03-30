from typing import List
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import verify_credentials
from crud.kiosk import (
    register_kiosk,
    get_kiosk_by_api_key,
    get_all_kiosks,
)
from schemas.kiosk import (
    KioskRegisterRequest,
    KioskRegisterResponse,
    KioskVerifyRequest,
    KioskResponse,
)

router = APIRouter(prefix="/kiosks", tags=["Kiosk"])


async def get_current_kiosk(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """X-API-Key 헤더로 키오스크를 인증합니다."""
    kiosk = await get_kiosk_by_api_key(db, x_api_key)
    if not kiosk or not kiosk.is_active:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return kiosk


@router.post("/register", response_model=KioskRegisterResponse)
async def register(
    data: KioskRegisterRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """키오스크 등록 + API 키 발급. 관리자 인증 필요."""
    kiosk = await register_kiosk(db, name=data.name, location=data.location)
    return KioskRegisterResponse(
        id=kiosk.id,
        name=kiosk.name,
        location=kiosk.location,
        api_key=kiosk.api_key,
    )


@router.post("/verify", response_model=KioskResponse)
async def verify(data: KioskVerifyRequest, db: AsyncSession = Depends(get_db)):
    """키오스크 기기 확인. 프런트 시작 시 호출."""
    kiosk = await get_kiosk_by_api_key(db, data.api_key)
    if not kiosk or not kiosk.is_active:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return kiosk


@router.get("", response_model=List[KioskResponse])
async def list_kiosks(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """전체 키오스크 목록. 관리자 인증 필요."""
    return await get_all_kiosks(db)
