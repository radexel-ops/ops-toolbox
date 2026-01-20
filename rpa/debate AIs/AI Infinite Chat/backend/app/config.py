"""Application configuration using Pydantic Settings"""

from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # AI API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

    # Web Search API Keys
    serper_api_key: Optional[str] = None  # Serper.dev (Google Search Results)
    google_cse_id: Optional[str] = None   # Google Custom Search Engine ID

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # CORS settings - allow all origins in development
    cors_origins: list[str] = ["*"]

    # Chat settings
    default_model: str = "gpt-5-mini"
    max_tokens: int = 4096
    temperature: float = 0.7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
