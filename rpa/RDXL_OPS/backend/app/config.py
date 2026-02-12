"""
VibeOps Configuration

Manages all application settings via environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional
import os
import secrets


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False  # Default to False for security
    ALLOWED_ORIGIN: str = "http://localhost:3000"

    # Database
    DATABASE_PATH: str = "./data/vibeops.db"

    # JWT Authentication - SECRET_KEY is REQUIRED in production
    SECRET_KEY: str = ""  # Must be set via environment variable
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SESSION_EXPIRY_HOURS: int = 24

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """
        Validate SECRET_KEY:
        - In production (DEBUG=False): Must be at least 32 characters
        - In development (DEBUG=True): Generate a random key if not provided
        """
        # Check if DEBUG is set to True in environment
        debug_mode = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")

        if not v or v == "":
            if debug_mode:
                # Generate a secure random key for development
                generated_key = secrets.token_urlsafe(32)
                print("⚠️  WARNING: Using auto-generated SECRET_KEY for development.")
                print("⚠️  Set SECRET_KEY environment variable for production!")
                return generated_key
            else:
                raise ValueError(
                    "SECRET_KEY environment variable is required in production. "
                    "Set DEBUG=true for development mode or provide a secure SECRET_KEY (min 32 chars)."
                )

        if len(v) < 32:
            raise ValueError(
                f"SECRET_KEY must be at least 32 characters long (got {len(v)}). "
                "Generate a secure key with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )

        return v

    # Project Paths
    PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    TEAMS_DIR: str = "teams"
    KNOWLEDGE_DIR: str = "knowledge"
    MASTER_CLAUDE_MD: str = "CLAUDE.md"

    # Douzone
    DOUZONE_USERNAME: Optional[str] = None
    DOUZONE_PASSWORD: Optional[str] = None
    DOUZONE_COMPANY_CODE: Optional[str] = None

    # Slack
    SLACK_WEBHOOK_URL: Optional[str] = None
    SLACK_CHANNEL: str = "#vibeops-alerts"

    # Claude API
    ANTHROPIC_API_KEY: Optional[str] = None

    # News
    NEWS_KEYWORDS: str = "AI,자동화,RPA"
    NEWS_SOURCES: str = "naver,google"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/vibeops.log"

    # Tmux
    TMUX_SESSION_NAME: str = "vibeops"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def teams_path(self) -> str:
        """Full path to teams directory"""
        return os.path.join(self.PROJECT_ROOT, self.TEAMS_DIR)

    @property
    def master_claude_path(self) -> str:
        """Full path to master CLAUDE.md"""
        return os.path.join(self.PROJECT_ROOT, self.MASTER_CLAUDE_MD)

    @property
    def master_knowledge_path(self) -> str:
        """Full path to master knowledge directory"""
        return os.path.join(self.PROJECT_ROOT, self.KNOWLEDGE_DIR)


# Global settings instance
settings = Settings()
