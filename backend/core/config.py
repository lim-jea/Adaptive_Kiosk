from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # HTTP Basic Auth (Swagger + 관리자 API 보호용)
    KIOSK_USERNAME: str = ""
    KIOSK_PASSWORD: str = ""
    ADMIN_API_KEY: str = ""

    # Database
    DATABASE_CONN: str = ""

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
    # "*" 입력 시 모든 오리진 허용 (개발 환경용)
    ALLOWED_ORIGINS: str = "*"

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
