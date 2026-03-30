import secrets
import enum
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from core.config import settings
from sqlalchemy import text
from core.database import get_session_factory, initialize_connection_pool

# ─── 토큰 만료 시간 ───
ACCESS_TOKEN_EXP_TIME = 1        # hours
REFRESH_TOKEN_EXP_TIME = 24 * 7  # hours (7일)

# ─── HTTP Basic Auth (docs 보호용) ───
http_basic = HTTPBasic()


def verify_credentials(credentials: HTTPBasicCredentials = Depends(http_basic)):
    correct_username = secrets.compare_digest(credentials.username, settings.KIOSK_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, settings.KIOSK_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


# ─── Enums ───
class UserType(enum.Enum):
    TEACHER = "teacher"
    STUDENT = "student"


class LangType(enum.Enum):
    KO = "ko"
    EN = "en"


class TokenType(enum.Enum):
    ACCESS = "access"
    REFRESH = "refresh"


# ─── Token Payload ───
class TokenPayload:
    def __init__(
        self,
        t_assoc: str,
        t_id: str,
        t_user_type: UserType,
        t_lang_type: LangType,
        is_admin: int,
    ):
        self.T_ASSOC = t_assoc
        self.T_ID = t_id
        self.T_USER_TYPE = t_user_type
        self.T_LANG_TYPE = t_lang_type
        self.is_admin = is_admin


# ─── 토큰 생성 / 검증 ───
def create_token(payload: dict, exp: int) -> str:
    payload = payload.copy()
    payload["exp"] = int(
        (datetime.now(timezone.utc) + timedelta(hours=exp)).timestamp()
    )
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False},
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def verify_token(token: str) -> bool:
    try:
        decoded = decode_token(token)
        if decoded is None:
            return False
        exp = decoded.get("exp")
        if exp is None:
            return False
        exp_time = datetime.fromtimestamp(exp, tz=timezone.utc)
        return exp_time > datetime.now(timezone.utc)
    except HTTPException:
        return False


def create_access_token(payload: dict) -> str:
    return create_token(payload, ACCESS_TOKEN_EXP_TIME)


def create_refresh_token(payload: dict) -> str:
    return create_token(payload, REFRESH_TOKEN_EXP_TIME)


def refresh_access_token(refresh_token: str) -> str:
    if not verify_token(refresh_token):
        raise HTTPException(status_code=401, detail="refresh token expired")
    decoded = decode_token(refresh_token)
    return create_access_token(decoded)


def save_token(
    response, token: str, save_as: TokenType, cookie_path: Optional[str] = None
):
    if save_as is TokenType.ACCESS:
        response.set_cookie(
            key="access_token",
            value=token,
            secure=True,
            samesite="None",
            httponly=True,
            path=cookie_path if cookie_path else "/",
        )
    elif save_as is TokenType.REFRESH:
        response.set_cookie(
            key="refresh_token",
            value=token,
            secure=True,
            samesite="None",
            httponly=True,
            path=cookie_path if cookie_path else "/",
        )


async def verify_access_token(access_token: str, refresh_token: str, response) -> str:
    if not access_token or not refresh_token:
        raise HTTPException(
            status_code=401, detail="access token or refresh token is missing"
        )

    decoded_access_token = decode_token(access_token)
    if not decoded_access_token:
        if not verify_token(refresh_token):
            raise HTTPException(
                status_code=401,
                detail="access token and refresh token are invalid or expired",
            )
        new_access_token = refresh_access_token(refresh_token)
        decoded_access_token = decode_token(new_access_token)
        new_cookie_path = (
            "/"
            + decoded_access_token.get("T_LANG_TYPE", "")
            + "/"
            + decoded_access_token.get("T_USER_TYPE", "")
        )
        response.delete_cookie("access_token")
        save_token(
            response, new_access_token, TokenType.ACCESS, cookie_path=new_cookie_path
        )
        access_token = new_access_token

    decoded_refresh_token = decode_token(refresh_token)
    if not decoded_refresh_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user_id = decoded_refresh_token.get("T_ID")
    assoc = decoded_refresh_token.get("T_ASSOC")
    user_type = decoded_refresh_token.get("T_USER_TYPE")

    try:
        factory = get_session_factory()
        if factory is None:
            await initialize_connection_pool()
            factory = get_session_factory()
        async with factory() as session:
            if user_type == UserType.STUDENT.value:
                sql = text(
                    "SELECT REFRESH_TOKEN FROM std_copy_copy WHERE userID = :uid AND S_ASSOC = :assoc"
                )
            else:
                sql = text(
                    "SELECT REFRESH_TOKEN FROM coala_teacher_copy WHERE T_ID = :uid AND T_ASSOC = :assoc"
                )
            result = await session.execute(sql, {"uid": user_id, "assoc": assoc})
            row = result.mappings().first()
            if not row or row["REFRESH_TOKEN"] != refresh_token:
                raise HTTPException(status_code=401, detail="Invalid refresh token")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Database error")

    if not verify_token(access_token):
        if not verify_token(refresh_token):
            raise HTTPException(status_code=401, detail="refresh token expired")
        new_access_token = refresh_access_token(refresh_token)
        decoded_access_token = decode_token(new_access_token)
        new_cookie_path = (
            "/"
            + decoded_access_token.get("T_LANG_TYPE", "")
            + "/"
            + decoded_access_token.get("T_USER_TYPE", "")
        )
        save_token(
            response, new_access_token, TokenType.ACCESS, cookie_path=new_cookie_path
        )
        access_token = new_access_token

    return access_token
