from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_CONN = os.getenv("DATABASE_CONN")
#QueuPool을 없애야 기본값인 AsyncdQueuePool로 작동한다.
engine = create_async_engine(DATABASE_CONN, echo=True, 
                       pool_size=10, max_overflow=0,
                       pool_recycle=300)

async def direct_get_conn():
    conn = None
    try:
        conn = await engine.connect()
        return conn
    except SQLAlchemyError as e:
        print(e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="요청하신 서비스가 잠시 이용 불가능합니다. 잠시 후 다시 시도해주세요.")
    
    
async def context_get_conn():
    conn = None
    try:
        conn = await engine.connect()
        yield conn
    except SQLAlchemyError as e:
        print(e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="요청하신 서비스가 잠시 이용 불가능합니다. 잠시 후 다시 시도해주세요.")
    finally:
        if conn:
            await conn.close()