import logging
import ssl
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

_engine = None
_async_session_factory = None


def get_engine():
    return _engine


def get_session_factory():
    return _async_session_factory


async def initialize_connection_pool():
    """
    SQLAlchemy async 엔진(커넥션 풀)을 초기화합니다.
    서버 시작 시(lifespan) 한 번 호출됩니다.
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
        # SSL: 클라우드 DB (Aiven 등) 자동 감지
        connect_args = {}
        if "aivencloud" in settings.DATABASE_CONN or "tidbcloud" in settings.DATABASE_CONN or "ssl" in settings.DATABASE_CONN.lower():
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ssl_ctx

        _engine = create_async_engine(
            settings.DATABASE_CONN,
            poolclass=AsyncAdaptedQueuePool,
            # ─── 커넥션 풀 튜닝 ───
            pool_size=5,            # 유지할 기본 연결 수 (클라우드 무료는 동시 연결 제한)
            max_overflow=5,         # 초과 시 임시 연결
            pool_timeout=30,        # 연결 대기 최대 시간
            pool_recycle=600,       # 10분마다 연결 재활용 (클라우드 idle timeout 대비)
            pool_pre_ping=True,     # 사용 전 연결 유효성 체크 (끊긴 연결 자동 복구)
            connect_args=connect_args,
        )

        # 풀 워밍업: 서버 시작 시 연결을 미리 만들어둠
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info(
            "SQLAlchemy Async Connection Pool initialized successfully. "
            "(pool_size=5, max_overflow=5, pool_pre_ping=True)"
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
    """FastAPI Depends용 async DB 세션 제너레이터."""
    factory = get_session_factory()
    if factory is None:
        await initialize_connection_pool()
        factory = get_session_factory()
    async with factory() as session:
        yield session
