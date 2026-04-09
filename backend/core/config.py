from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # HTTP Basic Auth (Swagger + 관리자 API 보호용)
    KIOSK_USERNAME: str = ""
    KIOSK_PASSWORD: str = ""

    # Database
    DATABASE_CONN: str = ""

    # Google Gemini (음성 주문용)
    GENAI_API_KEY: str = ""
    # Gemini TTS — preview가 실제 동작하는 모델명. GA명은 아직 없음.
    GENAI_TTS_MODEL: str = "gemini-2.5-flash-preview-tts"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
