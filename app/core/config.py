import os
from typing import Optional, List

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/chatdb")

    # Security
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    encryption_key: str = os.getenv("ENCRYPTION_KEY", "your-encryption-key-change-in-production")
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

    # Google OAuth
    google_client_id: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")


    # CORS
    # cors_origins: List[str] = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")

    # API Keys for providers (optional - users can provide their own)
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    mistral_api_key: Optional[str] = os.getenv("MISTRAL_API_KEY")

    # App
    app_name: str = os.getenv("APP_NAME", "Teehee Chat Backend")
    debug: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

    # Streaming
    max_tokens: int = int(os.getenv("MAX_TOKENS", 4096))
    stream_timeout: int = int(os.getenv("STREAM_TIMEOUT", 300))  # 5 minutes


settings = Settings() 