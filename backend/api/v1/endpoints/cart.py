from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.session_auth import verify_session_token
from schemas import CartReplaceRequest, CartResponse
from services.cart_service import clear_cart, get_cart_response, replace_cart

router = APIRouter(prefix="/carts", tags=["Cart"])


@router.get(
    "/{session_uuid}",
    response_model=CartResponse,
    dependencies=[Depends(verify_session_token)],
)
async def read_cart(session_uuid: str, db: AsyncSession = Depends(get_db)):
    return await get_cart_response(db, session_uuid)


# PUT 에는 debounce 를 걸지 않는다 — 사용자가 + / − 버튼을 빠르게 누를 때 (e.g. 1→6 까지 5번 클릭)
# 0.3 초 debounce 가 PUT 일부를 429 로 막아 서버 카트와 로컬이 어긋날 수 있다.
# 카트 쓰기는 외부 API 가 아닌 DB JSON 컬럼 갱신뿐이고 세션 토큰 검증으로 abuse 가 차단되므로
# 별도 rate limit 없이도 안전하다.
@router.put(
    "/{session_uuid}",
    response_model=CartResponse,
    dependencies=[Depends(verify_session_token)],
)
async def replace_cart_endpoint(
    session_uuid: str,
    req: CartReplaceRequest,
    db: AsyncSession = Depends(get_db),
):
    return await replace_cart(db, session_uuid, req)


@router.delete(
    "/{session_uuid}",
    response_model=CartResponse,
    dependencies=[Depends(verify_session_token)],
)
async def clear_cart_endpoint(session_uuid: str, db: AsyncSession = Depends(get_db)):
    return await clear_cart(db, session_uuid)
