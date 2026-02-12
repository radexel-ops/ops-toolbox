"""
FastAPI Dependencies

Dependency injection for authentication, authorization, and database.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from .database import get_db
from .services.auth_service import auth_service
from .models import User, UserRole


# Security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.

    Raises HTTPException if token is invalid or user not found.
    """
    token = credentials.credentials
    payload = auth_service.decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = int(payload.get("sub"))
    user = await auth_service.get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Alias for get_current_user (explicit active check)"""
    return current_user


async def get_super_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require super admin privileges.

    Raises HTTPException if user is not super admin.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required"
        )
    return current_user


async def get_team_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require team admin or higher privileges.

    Raises HTTPException if user is not at least team admin.
    """
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.TEAM_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team admin privileges required"
        )
    return current_user


# Alias for admin requirement
require_admin = get_team_admin


class TeamAccessChecker:
    """
    Dependency class for checking team access.

    Usage:
        @router.get("/teams/{team_id}/...")
        async def endpoint(
            team_id: int,
            user: User = Depends(TeamAccessChecker())
        ):
            pass
    """

    def __init__(self, require_admin: bool = False):
        self.require_admin = require_admin

    async def __call__(
        self,
        team_id: int,
        current_user: User = Depends(get_current_user)
    ) -> User:
        # Super admin can access all teams
        if current_user.role == UserRole.SUPER_ADMIN:
            return current_user

        # Check if user belongs to this team
        if current_user.team_id != team_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this team"
            )

        # Check admin requirement
        if self.require_admin and current_user.role != UserRole.TEAM_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Team admin privileges required"
            )

        return current_user


class GuidelineEditChecker:
    """
    Dependency for checking guideline edit permissions.

    Master guidelines: super_admin only
    Team guidelines: team_admin of that team or super_admin
    """

    def __init__(self, is_master: bool = False):
        self.is_master = is_master

    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        team_id: Optional[int] = None
    ) -> User:
        if self.is_master:
            # Master guidelines require super_admin
            if not current_user.can_edit_master_guidelines():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only super admin can edit master guidelines"
                )
        else:
            # Team guidelines require team_admin or super_admin
            if team_id and not current_user.can_edit_team_guidelines(team_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You cannot edit this team's guidelines"
                )

        return current_user
