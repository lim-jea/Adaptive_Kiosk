import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from core.config import settings

# ─── HTTP Basic Auth ───
# Swagger 문서(/docs, /redoc) 및 관리자 전용 엔드포인트(analytics, kiosk register/list) 보호용.
# .env의 KIOSK_USERNAME / KIOSK_PASSWORD로 인증.
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
