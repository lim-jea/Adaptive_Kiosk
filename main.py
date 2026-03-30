import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from fastapi.responses import JSONResponse

from core.database import Base, get_engine, initialize_connection_pool
import secrets
from core.config import settings
from core.security import http_basic
from api.v1.router import v1_router

# 모델 임포트 (Base.metadata에 테이블 등록)
import models  # noqa: F401

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 이벤트"""
    try:
        await initialize_connection_pool()
        # DB 연결 성공 시 테이블 자동 생성
        engine = get_engine()
        if engine is not None:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully.")
    except Exception as e:
        logger.warning("Database initialization skipped: %s", e)
    yield


app = FastAPI(
    title="Adaptive Kiosk API",
    description="카메라 기반 사용자 인식 + 음료 추천 + 주문 관리",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS 미들웨어 (기존 설정 유지) ───
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:8000",
    "http://localhost:8080",
    "http://localhost:5000",
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
