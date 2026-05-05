import secrets

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from core.config import settings

# ─── HTTP Basic Auth ───
# Swagger 문서(/docs, /redoc) 및 관리자 전용 엔드포인트(analytics, kiosk register/list) 보호용.
# .env의 KIOSK_USERNAME / KIOSK_PASSWORD로 인증.
http_basic = HTTPBasic(auto_error=False)


def verify_credentials(
    credentials: HTTPBasicCredentials | None = Depends(http_basic),
    x_admin_api_key: str | None = Header(None, alias="X-Admin-API-Key"),
):
    if settings.ADMIN_API_KEY and x_admin_api_key:
        if secrets.compare_digest(x_admin_api_key, settings.ADMIN_API_KEY):
            return

    if credentials is not None:
        correct_username = secrets.compare_digest(credentials.username, settings.KIOSK_USERNAME)
        correct_password = secrets.compare_digest(credentials.password, settings.KIOSK_PASSWORD)
        if correct_username and correct_password:
            return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid admin credentials",
        headers={"WWW-Authenticate": "Basic"},
    )
