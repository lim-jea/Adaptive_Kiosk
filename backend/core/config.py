from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # HTTP Basic Auth (Swagger + 관리자 API 보호용)
    KIOSK_USERNAME: str = ""
    KIOSK_PASSWORD: str = ""

    # Database
    DATABASE_CONN: str = ""

    # Google Gemini (음성 주문용)
    GENAI_API_KEY: str = ""

    # Google Gemini TTS (선택 기능)
    # - 기본은 False: 디스크 캐시에 없으면 None 반환 → 프런트가 브라우저 TTS로 폴백
    # - True면 캐시 미스 시 Gemini TTS를 호출해 WAV를 저장/반환한다.
    GENAI_TTS_ENABLED: bool = False
    GENAI_TTS_MODEL: str = "gemini-2.5-flash-preview-tts"
    GENAI_TTS_LANGUAGE_CODE: str = "ko-KR"
    GENAI_TTS_VOICE_NAME: str = "kore"

    # Naver DataLab API - 실시간 트렌드 조회
    NAVER_TREND_ENABLED: bool = True
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""
    TREND_CACHE_TTL: int = 3600  # 초 단위 (기본 1시간)

    RECOMMENDATION_BOOTSTRAP_ON_STARTUP: bool = True
    RECOMMENDATION_BOOTSTRAP_BATCH_SIZE: int = 2000
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
    }


settings = Settings()
