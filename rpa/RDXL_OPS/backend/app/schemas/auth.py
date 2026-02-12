"""
Authentication Pydantic Schemas

JWT token validation schemas.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Token(BaseModel):
    """Schema for access token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenPayload(BaseModel):
    """Schema for JWT token payload"""
    sub: int  # user_id
    email: str
    role: str
    team_id: Optional[int] = None
    team_slug: Optional[str] = None
    exp: datetime
    iat: datetime


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request"""
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """Schema for password change"""
    current_password: str
    new_password: str
