import asyncio
import sys
import logging
from contextlib import asynccontextmanager

# Windows + aiomysql + SSL 호환을 위해 SelectorEventLoop 사용
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from fastapi.responses import JSONResponse

from core.database import Base, get_engine, get_session_factory, initialize_connection_pool
import secrets
from core.config import settings
from core.security import http_basic
from api.v1.router import v1_router
from scripts.seed_menu import seed_menu_data
from services.face_service import face_service
from services.chat_service import prewarm_tts_cache
from services.trend_service import initialize_trend_service
from services.recommendation_service import initialize_recommendation_engine, get_recommendation_engine

# 모델 임포트 (Base.metadata에 테이블 등록)
import models  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Set specific loggers to INFO to see API call logs
logging.getLogger("services.trend_service").setLevel(logging.INFO)
logging.getLogger("services.recommendation_service").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 이벤트"""
    # 얼굴 분석 모델 로드 (mock 모드 가능)
    try:
        await face_service.load_models()
    except Exception as e:
        logger.warning("Face service load failed: %s", e)

    try:
        await initialize_connection_pool()
        # DB 연결 성공 시 테이블 자동 생성
        engine = get_engine()
        if engine is not None:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully.")

            # 시드 데이터 삽입 (카테고리, 메뉴, 옵션)
            factory = get_session_factory()
            if factory:
                async with factory() as db:
                    await seed_menu_data(db)

                # 📊 추천 통계 배치 프로세스 (서버 시작 시 한 번만 실행)
                logger.info("🔄 추천 통계 배치 시작...")
                engine = get_recommendation_engine()
                stats, metadata = await engine.precompute_all_stats()

                if stats and metadata:
                    logger.info("✓ 배치 완료, 캐시 로드 중...")

                    # 메뉴 정보 캐시 (DB에서 가져오기)
                    async with factory() as db:
                        await initialize_recommendation_engine(db)

                    # 사전 계산된 통계 로드
                    if engine.load_cached_stats(stats, metadata):
                        logger.info("✅ 추천 시스템 준비 완료 (캐시 활성화)")
                    else:
                        logger.warning("캐시 로드 실패, Fallback 모드로 실행")
                else:
                    logger.warning("배치 실패, Fallback 모드로 실행")
                    # Fallback: 기존 CSV 로드 방식으로 진행
                    async with factory() as db:
                        await initialize_recommendation_engine(db)
    except Exception as e:
        logger.warning("Database initialization skipped: %s", e)
    
    # 트렌드 서비스 초기화 (추천 엔진과 독립적)
    try:
        if initialize_trend_service():
            logger.info("✓ Trend service initialized")
        else:
            logger.warning("Trend service not available")
    except Exception as e:
        logger.warning("Trend service initialization failed: %s", e)

    # TTS 프리워밍 — 시나리오 + 템플릿×DB 메뉴/옵션 조합을 미리 합성해 디스크 캐시에 적재
    # 백그라운드로 띄워서 서버 부팅을 막지 않음
    asyncio.create_task(prewarm_tts_cache(get_session_factory()))
    yield


app = FastAPI(
    title="Adaptive Kiosk API",
    description="카메라 기반 사용자 인식 + 음료 추천 + 주문 관리",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS 미들웨어 ───
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:5000",
    "http://localhost:5173",  # Vite 기본 포트 (프런트엔드)
    "http://localhost:8000",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Docs 보호 미들웨어 ───
# /docs, /redoc 진입 시에만 인증. /openapi.json은 인증 후 브라우저 캐시로 접근하므로 제외.
PROTECTED_DOC_PATHS = {"/docs", "/docs/", "/redoc", "/redoc/"}

@app.middleware("http")
async def docs_protect_middleware(request: Request, call_next):
    if request.url.path in PROTECTED_DOC_PATHS:
        try:
            credentials = await http_basic(request)
            if not (
                secrets.compare_digest(credentials.username, settings.KIOSK_USERNAME)
                and secrets.compare_digest(credentials.password, settings.KIOSK_PASSWORD)
            ):
                raise HTTPException(status_code=401)
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid credentials"},
                headers={"WWW-Authenticate": "Basic"},
            )
    response = await call_next(request)
    return response


# ─── 라우터 등록 ───
app.include_router(v1_router)


# ─── 기본 헬스 체크 ───
@app.get("/")
async def root():
    return {"message": "Adaptive Kiosk API is running"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}
