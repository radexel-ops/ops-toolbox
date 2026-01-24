"""Application configuration using Pydantic Settings"""

from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv
import os

# .env 파일 로드 (로컬 개발 환경용)
# Docker 환경에서는 환경변수가 직접 주입되므로 파일이 없어도 됨
try:
    # 로컬 개발: 상위 폴더의 .env 파일들
    # config.py -> app -> backend -> AI Infinite Chat -> debate AIs -> rpa -> RDXL_RPA
    _root = Path(__file__).resolve().parent.parent.parent.parent.parent.parent  # 6단계 상위 = RDXL_RPA
    if (_root / '.env.shared').exists():
        load_dotenv(_root / '.env.shared')
    if (_root / '.env.local').exists():
        load_dotenv(_root / '.env.local', override=True)

    # Docker/프로덕션: backend 폴더의 .env 파일
    _backend_root = Path(__file__).resolve().parent.parent  # backend/app -> backend
    if (_backend_root / '.env').exists():
        load_dotenv(_backend_root / '.env', override=True)
except Exception:
    pass  # 환경변수는 Docker에서 직접 주입됨


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
