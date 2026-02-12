"""
Authentication Router

Handles login, logout, token refresh, and password management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from slowapi import Limiter
from slowapi.util import get_remote_address

from ..database import get_db
from ..services.auth_service import auth_service
from ..schemas.user import UserLogin, UserResponse
from ..schemas.auth import Token, RefreshTokenRequest, PasswordChangeRequest
from ..dependencies import get_current_user
from ..models import User
from ..config import settings

router = APIRouter()

# Rate limiter for auth endpoints
limiter = Limiter(key_func=get_remote_address)


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")  # Max 5 login attempts per minute
async def login(
    request: Request,  # Required by rate limiter
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user and return JWT tokens.

    Returns access_token (short-lived) and refresh_token (long-lived).

    Rate limited: 5 attempts per minute per IP address.
    """
    # Get client info
    user_agent = request.headers.get("User-Agent")
    client_ip = request.client.host if request.client else None

    # Attempt login
    result = await auth_service.login(
        db,
        email=login_data.email,
        password=login_data.password,
        user_agent=user_agent,
        ip_address=client_ip
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token, refresh_token, user = result

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    Returns new access_token and refresh_token.
    Old refresh_token is invalidated.
    """
    result = await auth_service.refresh_tokens(db, refresh_data.refresh_token)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token, refresh_token = result

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout")
async def logout(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Logout by invalidating refresh token.
    """
    success = await auth_service.logout(db, refresh_data.refresh_token)

    return {
        "success": success,
        "message": "Logged out successfully" if success else "Token not found"
    }


@router.post("/logout-all")
async def logout_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Logout from all devices by invalidating all refresh tokens.

    Requires authentication.
    """
    count = await auth_service.logout_all(db, current_user.id)

    return {
        "success": True,
        "message": f"Logged out from {count} sessions"
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user's information.
    """
    team_name = None
    if current_user.team:
        team_name = current_user.team.name

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role.value,
        team_id=current_user.team_id,
        team_name=team_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login=current_user.last_login
    )


@router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change current user's password.

    Requires current password verification.
    """
    success = await auth_service.change_password(
        db,
        user=current_user,
        current_password=password_data.current_password,
        new_password=password_data.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    return {
        "success": True,
        "message": "Password changed successfully"
    }
