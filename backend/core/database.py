import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import AsyncAdaptedQueuePool
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from core.config import settings

logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """데이터베이스 연결 또는 풀 관련 오류를 위한 커스텀 예외"""
    pass


Base = declarative_base()

# 모듈 내부 상태 (외부에서 직접 import하지 않고 함수로 접근)
_engine = None
_async_session_factory = None


def get_engine():
    """현재 엔진을 반환합니다."""
    return _engine


def get_session_factory():
    """현재 세션 팩토리를 반환합니다."""
    return _async_session_factory


async def initialize_connection_pool():
    """
    SQLAlchemy async 엔진(커넥션 풀)을 초기화합니다.
    애플리케이션 시작 시(lifespan) 한 번 호출되어야 합니다.
    """
    global _engine, _async_session_factory

    if _engine is not None:
        logger.info("Connection pool is already initialized.")
        return

    if not settings.DATABASE_CONN:
        msg = "Missing required environment variable: DATABASE_CONN"
        logger.error(msg)
        raise ValueError(msg)

    try:
        _engine = create_async_engine(
            settings.DATABASE_CONN,
            poolclass=AsyncAdaptedQueuePool,
            pool_size=32,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=1800,
        )

        # 테스트 연결 후 명시적으로 풀 정리하여 aiomysql GC 경고 방지
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info(
            "SQLAlchemy Async Connection Pool initialized successfully. "
            "(pool_size=32, max_overflow=20, pool_timeout=30s)"
        )

        _async_session_factory = async_sessionmaker(
            bind=_engine, class_=AsyncSession, expire_on_commit=False
        )

    except OperationalError as e:
        logger.error("Failed to connect to database during initialization: %s", e)
        _engine = None
        raise DatabaseConnectionError(f"Failed to connect to database: {e}") from e
    except Exception as e:
        logger.error("Failed to create SQLAlchemy engine: %s", e)
        _engine = None
        raise DatabaseConnectionError(f"Failed to initialize pool: {e}") from e


async def get_db():
    """
    FastAPI Depends용 async DB 세션 제너레이터.
    """
    factory = get_session_factory()
    if factory is None:
        await initialize_connection_pool()
        factory = get_session_factory()
    async with factory() as session:
        yield session
