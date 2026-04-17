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

    model_config = {
        "env_file": (
            str(Path(__file__).resolve().parents[1] / ".env"),
            ".env",
        ),
        "env_file_encoding": "utf-8",
    }


settings = Settings()
