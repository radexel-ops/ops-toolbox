"""
Team Pydantic Schemas

Request/Response validation for team-related endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TeamBase(BaseModel):
    """Base team fields"""
    slug: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class TeamCreate(TeamBase):
    """Schema for creating a new team"""
    pass


class TeamUpdate(BaseModel):
    """Schema for updating team information"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class TeamResponse(TeamBase):
    """Schema for team response"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    member_count: int = 0

    class Config:
        from_attributes = True


class TeamListResponse(BaseModel):
    """Schema for team list"""
    total: int
    teams: list[TeamResponse]


class TeamGuidelineResponse(BaseModel):
    """Schema for team guideline response"""
    id: int
    team_id: int
    file_path: str
    content: Optional[str]
    is_main_guideline: bool
    updated_at: datetime
    updated_by: Optional[int]

    class Config:
        from_attributes = True


class TeamGuidelineUpdate(BaseModel):
    """Schema for updating team guideline"""
    content: str
