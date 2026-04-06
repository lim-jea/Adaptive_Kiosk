from fastapi import APIRouter

from api.v1.endpoints.kiosk import router as kiosk_router
from api.v1.endpoints.session import router as session_router
from api.v1.endpoints.menu import router as menu_router
from api.v1.endpoints.option import router as option_router
from api.v1.endpoints.order import router as order_router
from api.v1.endpoints.analytics import router as analytics_router
from api.v1.endpoints.face import router as face_router

v1_router = APIRouter(prefix="/api/v1")

# ─── 기본 키오스크 + 비전 API ───
v1_router.include_router(kiosk_router)
v1_router.include_router(session_router)
v1_router.include_router(menu_router)
v1_router.include_router(option_router)
v1_router.include_router(order_router)
v1_router.include_router(analytics_router)
v1_router.include_router(face_router)

# ─── 추후 활성화 (음성 주문 / 추천) ───
# from api.v1.endpoints.recommendation import router as recommendation_router
# from api.v1.endpoints.voice import router as voice_router
# v1_router.include_router(recommendation_router)
# v1_router.include_router(voice_router)
