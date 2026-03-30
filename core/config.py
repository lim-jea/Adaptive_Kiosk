from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # HTTP Basic Auth (docs 보호용)
    KIOSK_USERNAME: str = ""
    KIOSK_PASSWORD: str = ""

    # JWT
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"

    
    # Database Pool
    #POOL_NAME: str = ""
    #POOL_HOST: str = ""
    #POOL_USER: str = ""
    #POOL_PASSWORD: str = ""
    #POOL_DATABASE: str = ""
    DATABASE_CONN: str = ""

    # Redis (추후 활성화)
    #REDIS_HOST: str = ""
    #REDIS_PORT: str = ""
    #REDIS_PASSWORD: str = ""

    # GenAI (추후 활성화)
    GENAI_API_KEY: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
