from typing import List
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.kiosk import (
    register_kiosk,
    get_kiosk_by_api_key,
    get_kiosk_by_id,
    get_all_kiosks,
    update_last_seen,
)
from schemas.kiosk import (
    KioskRegister,
    KioskRegisterResponse,
    KioskLoginRequest,
    KioskResponse,
)

router = APIRouter(prefix="/kiosks", tags=["Kiosk"])


async def get_current_kiosk(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """
    X-API-Key 헤더로 키오스크를 인증합니다.
    키오스크 프런트에서 모든 API 호출 시 이 헤더를 포함합니다.
    """
    kiosk = await get_kiosk_by_api_key(db, x_api_key)
    if not kiosk or not kiosk.is_active:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    await update_last_seen(db, kiosk)
    return kiosk


@router.post("/register", response_model=KioskRegisterResponse)
async def register(data: KioskRegister, db: AsyncSession = Depends(get_db)):
    """
    새 키오스크를 등록합니다. 발급된 API 키를 키오스크 프런트에 저장해야 합니다.
    (관리자가 호출)
    """
    kiosk = await register_kiosk(db, name=data.name, location=data.location)
    return KioskRegisterResponse(
        id=kiosk.id,
        name=kiosk.name,
        location=kiosk.location,
        api_key=kiosk.api_key,
    )


@router.post("/login", response_model=KioskResponse)
async def login(data: KioskLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    키오스크 로그인 (API 키 유효성 확인 + last_seen 갱신).
    프런트 시작 시 호출하여 인증 상태를 확인합니다.
    """
    kiosk = await get_kiosk_by_api_key(db, data.api_key)
    if not kiosk or not kiosk.is_active:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    await update_last_seen(db, kiosk)
    return kiosk


@router.get("", response_model=List[KioskResponse])
async def list_kiosks(db: AsyncSession = Depends(get_db)):
    """등록된 전체 키오스크 목록을 조회합니다."""
    return await get_all_kiosks(db)


@router.get("/{kiosk_id}", response_model=KioskResponse)
async def read_kiosk(kiosk_id: int, db: AsyncSession = Depends(get_db)):
    """특정 키오스크 정보를 조회합니다."""
    kiosk = await get_kiosk_by_id(db, kiosk_id)
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")
    return kiosk
