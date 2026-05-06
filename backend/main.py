import asyncio
import logging
import secrets
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

from api.v1.router import v1_router
from core.config import settings
from core.database import (
    Base,
    get_engine,
    get_session_factory,
    initialize_connection_pool,
)
from core.security import http_basic
from scripts.bootstrap_recommendation_data import bootstrap_recommendation_csv_to_db
from scripts.seed_menu import seed_menu_data
from services.face_service import face_service
from services.recommendation_service import (
    get_recommendation_engine,
    initialize_recommendation_engine,
)
from services.trend_service import initialize_trend_service

import model  # noqa: F401


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("services.trend_service").setLevel(logging.INFO)
logging.getLogger("services.recommendation_service").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    try:
        await face_service.load_models()
    except Exception as exc:
        logger.warning("Face service load failed: %s", exc)

    try:
        await initialize_connection_pool()
        engine = get_engine()
        if engine is not None:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully.")

            factory = get_session_factory()
            if factory:
                async with factory() as db:
                    await seed_menu_data(db)
                    if settings.RECOMMENDATION_BOOTSTRAP_ON_STARTUP:
                        await bootstrap_recommendation_csv_to_db(db)
                    else:
                        logger.info(
                            "Recommendation CSV bootstrap skipped by env setting "
                            "(RECOMMENDATION_BOOTSTRAP_ON_STARTUP=false)"
                        )

                logger.info("Starting recommendation stats batch...")
                recommendation_engine = get_recommendation_engine()
                stats, metadata = await recommendation_engine.precompute_all_stats()

                if stats and metadata:
                    logger.info("Recommendation stats batch finished. Loading cache...")
                    async with factory() as db:
                        await initialize_recommendation_engine(db)

                    if recommendation_engine.load_cached_stats(stats):
                        logger.info("Recommendation system ready (cache enabled)")
                    else:
                        logger.warning("Recommendation cache load failed. Using fallback mode.")
                else:
                    logger.warning("Recommendation stats batch failed. Using fallback mode.")
                    async with factory() as db:
                        await initialize_recommendation_engine(db)
    except Exception as exc:
        logger.warning("Database initialization skipped: %s", exc)

    try:
        from services.trend_service import get_trend_service
        from model import Menu
        from sqlalchemy import select

        if settings.NAVER_TREND_ENABLED and initialize_trend_service():
            logger.info("Trend service initialized")

            factory = get_session_factory()
            if factory:
                async with factory() as db:
                    stmt = select(Menu).where(Menu.is_available == True)
                    result = await db.execute(stmt)
                    menus = result.scalars().all()

                menu_dicts = [{"name": m.name, "id": m.id} for m in menus]
                trend_service = get_trend_service()
                cached_count = trend_service.load_current_snapshot()

                if cached_count > 0:
                    logger.info("Trend snapshot loaded: %d cached weights", cached_count)
                else:
                    logger.info(
                        "No fresh trend snapshot. Starting 3-day trend precompute in background."
                    )
                    asyncio.create_task(trend_service.ensure_trends_ready(menu_dicts))
        elif settings.NAVER_TREND_ENABLED:
            logger.warning("Trend service not available")
        else:
            logger.info("Trend integration disabled by env setting")
    except Exception as exc:
        logger.warning("Trend service initialization failed: %s", exc)

    yield


app = FastAPI(
    title="Adaptive Kiosk API",
    description="Camera-based recognition, beverage recommendations, and order management API",
    version="1.0.0",
    lifespan=lifespan,
)


_origins = (
    ["*"]
    if settings.ALLOWED_ORIGINS.strip() == "*"
    else [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


PROTECTED_DOC_PATHS = {"/docs", "/docs/", "/redoc", "/redoc/"}


@app.middleware("http")
async def docs_protect_middleware(request: Request, call_next):
    if request.url.path in PROTECTED_DOC_PATHS:
        try:
            credentials = await http_basic(request)
            if not (
                credentials is not None
                and
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


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        if settings.REQUEST_TIMING_LOG_ENABLED:
            logger.exception(
                "HTTP %s %s -> 500 (%.1fms)",
                request.method,
                request.url.path,
                elapsed_ms,
            )
        raise

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"

    if settings.REQUEST_TIMING_LOG_ENABLED:
        level = logging.WARNING if elapsed_ms >= settings.REQUEST_TIMING_SLOW_MS else logging.INFO
        logger.log(
            level,
            "HTTP %s %s -> %s (%.1fms)%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            " [slow]" if elapsed_ms >= settings.REQUEST_TIMING_SLOW_MS else "",
        )

    return response


app.include_router(v1_router)


@app.get("/")
async def root():
    return {"message": "Adaptive Kiosk API is running"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}
