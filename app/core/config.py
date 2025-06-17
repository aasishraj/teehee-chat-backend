from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/chatdb"
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    encryption_key: str = "your-encryption-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    # API Keys for providers (optional - users can provide their own)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    
    # App
    app_name: str = "Teehee Chat Backend"
    debug: bool = False
    
    # Streaming
    max_tokens: int = 4096
    stream_timeout: int = 300  # 5 minutes


settings = Settings() 