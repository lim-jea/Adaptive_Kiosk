from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # HTTP Basic Auth (Swagger + 관리자 API 보호용)
    KIOSK_USERNAME: str = ""
    KIOSK_PASSWORD: str = ""
    ADMIN_API_KEY: str = ""

    # Database
    DATABASE_CONN: str = ""
    # MySQL SSL 검증 — Aiven/TiDB 등 클라우드 DB 사용 시.
    # "verify" : 인증서 검증 활성화 (운영 권장, DB_SSL_CA_PATH 필요)
    # "none"   : 검증 비활성 (개발 편의용, MITM 위험)
    DB_SSL_MODE: str = "none"
    DB_SSL_CA_PATH: str = ""

    # 쿠키 Secure 플래그 — HTTPS 환경에서는 True 권장.
    # 로컬 개발(http://localhost)에서는 False 로 설정해야 브라우저가 쿠키를 저장/전송한다.
    SECURE_COOKIES: bool = True

    # Google Gemini (음성 주문용)
    GENAI_API_KEY: str = ""

    # Edge-TTS (Microsoft Azure Neural 음성, 비공식). 무료 + 빠름 + 자연스러움.
    # 합성 실패/패키지 미설치 시 synthesize_speech 가 None 반환 → 프런트가 브라우저 TTS 로 폴백.
    EDGE_TTS_ENABLED: bool = True
    EDGE_TTS_VOICE: str = "ko-KR-SunHiNeural"   # 여성, 캡스톤 검증 결과 채택

    # Naver DataLab API - 실시간 트렌드 조회
    NAVER_TREND_ENABLED: bool = True
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""
    TREND_CACHE_TTL: int = 3600  # 초 단위 (기본 1시간)

    # CORS — 콤마 구분 목록 (예: https://kiosk.example.com,https://api.example.com)
    # 운영 환경은 반드시 명시적 도메인 화이트리스트로 설정해야 한다.
    # 빈 문자열이면 동일 출처만 허용 (Cloudflare Tunnel + 같은 도메인 프론트엔드의 정상 케이스).
    # "*" 는 개발 편의 외에 사용 금지.
    ALLOWED_ORIGINS: str = ""

    STARTUP_DB_WRITE_ENABLED: bool = True
    RECOMMENDATION_BOOTSTRAP_ON_STARTUP: bool = True
    RECOMMENDATION_BOOTSTRAP_BATCH_SIZE: int = 2000
    REQUEST_TIMING_LOG_ENABLED: bool = True
    REQUEST_TIMING_SLOW_MS: int = 800
    RECOMMENDATION_PRECOMPUTE_LOG_INTERVAL: int = 500
    RECOMMENDATION_COPURCHASE_BATCH_SIZE: int = 1000

    # Face analysis
    FACE_MODEL_PATH: str = str(
        Path(__file__).resolve().parents[1] / "models" / "0424model.pth"
    )
    FACE_INSIGHTFACE_MODEL_NAME: str = "buffalo_l"
    FACE_USE_CUDA: bool = True
    FACE_DETECTION_WIDTH: int = 320
    FACE_DETECTION_HEIGHT: int = 320
    FACE_DETECTION_SCORE_THRESHOLD: float = 0.5
    FACE_MIN_FACE_SIZE: int = 120
    FACE_MIN_VALID_FRAMES: int = 5

    model_config = {
        "env_file": (
            str(Path(__file__).resolve().parents[1] / ".env"),
            ".env",
        ),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
