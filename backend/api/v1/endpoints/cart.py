from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from schemas import CartReplaceRequest, CartResponse
from services.cart_service import clear_cart, get_cart_response, replace_cart

router = APIRouter(prefix="/carts", tags=["Cart"])


@router.get("/{session_uuid}", response_model=CartResponse)
async def read_cart(session_uuid: str, db: AsyncSession = Depends(get_db)):
    return await get_cart_response(db, session_uuid)


@router.put("/{session_uuid}", response_model=CartResponse)
async def replace_cart_endpoint(
    session_uuid: str,
    req: CartReplaceRequest,
    db: AsyncSession = Depends(get_db),
):
    return await replace_cart(db, session_uuid, req)


@router.delete("/{session_uuid}", response_model=CartResponse)
async def clear_cart_endpoint(session_uuid: str, db: AsyncSession = Depends(get_db)):
    return await clear_cart(db, session_uuid)
