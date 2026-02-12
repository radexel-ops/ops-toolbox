"""
User Pydantic Schemas

Request/Response validation for user-related endpoints.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRoleEnum(str, Enum):
    """User role enumeration"""
    SUPER_ADMIN = "super_admin"
    TEAM_ADMIN = "team_admin"
    MEMBER = "member"


class UserBase(BaseModel):
    """Base user fields"""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)


class UserCreate(UserBase):
    """Schema for creating a new user"""
    password: str = Field(..., min_length=6, max_length=100)
    role: UserRoleEnum = UserRoleEnum.MEMBER
    team_id: Optional[int] = None


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[UserRoleEnum] = None
    team_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class UserResponse(UserBase):
    """Schema for user response"""
    id: int
    role: UserRoleEnum
    team_id: Optional[int]
    team_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Schema for paginated user list"""
    total: int
    users: list[UserResponse]
