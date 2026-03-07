from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://receipts:receipts@db:5432/receipts"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite-preview"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB
    IMAGE_DIR: str = "./data/images"
    MAX_REPAIR_RETRIES: int = 2

    # Google OAuth
    GOOGLE_CLIENT_ID: str = "68190317197-qghomcut33vm6cr46nukcj8s46jkh1ih.apps.googleusercontent.com"

    # JWT
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
