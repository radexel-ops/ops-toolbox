"""
Admin Router

Administrative endpoints for user management, feedback, and system configuration.
Requires admin privileges (super_admin or team_admin).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr

from ..database import get_db
from ..models import User, UserRole, Team
from ..models.feedback import Feedback, FeedbackStatus
from ..dependencies import get_current_user, require_admin

router = APIRouter()


# ==================== SCHEMAS ====================

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    team_id: Optional[int]
    team_name: Optional[str]
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int


class UserUpdate(BaseModel):
    name: Optional[str] = None
    team_id: Optional[int] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class TeamResponse(BaseModel):
    id: int
    name: str
    slug: str

    class Config:
        from_attributes = True


class FeedbackResponse(BaseModel):
    id: int
    user_id: int
    user_email: str
    title: Optional[str]
    content: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FeedbackUpdate(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None


class FeedbackCreate(BaseModel):
    title: Optional[str] = None
    content: str


# ==================== TEAMS ====================

@router.get("/teams", response_model=List[TeamResponse])
async def list_teams(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all teams"""
    result = await db.execute(select(Team).order_by(Team.name))
    teams = result.scalars().all()
    return teams


# ==================== PENDING USERS ====================

@router.get("/users/pending", response_model=List[UserResponse])
async def list_pending_users(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List users pending approval (is_active = False and never logged in)"""
    query = (
        select(User)
        .options(selectinload(User.team))
        .where(User.is_active == False)
        .where(User.last_login == None)
        .order_by(User.created_at.desc())
    )

    # Team admin can only see users from their team
    if not current_user.is_super_admin and current_user.team_id:
        query = query.where(User.team_id == current_user.team_id)

    result = await db.execute(query)
    users = result.scalars().all()

    return [
        UserResponse(
            id=u.id,
            email=u.email,
            name=u.name,
            role=u.role.value,
            team_id=u.team_id,
            team_name=u.team.name if u.team else None,
            is_active=u.is_active,
            created_at=u.created_at,
            last_login=u.last_login
        )
        for u in users
    ]


@router.post("/users/{user_id}/approve")
async def approve_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve a pending user"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check permission
    if not current_user.is_super_admin:
        if user.team_id != current_user.team_id:
            raise HTTPException(status_code=403, detail="Cannot approve user from different team")

    user.is_active = True
    await db.commit()

    return {"message": "User approved successfully"}


@router.post("/users/{user_id}/reject")
async def reject_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reject and delete a pending user"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check permission
    if not current_user.is_super_admin:
        if user.team_id != current_user.team_id:
            raise HTTPException(status_code=403, detail="Cannot reject user from different team")

    # Only reject pending users (not yet logged in)
    if user.last_login is not None:
        raise HTTPException(status_code=400, detail="Cannot reject user who has already logged in")

    await db.delete(user)
    await db.commit()

    return {"message": "User rejected and deleted"}


# ==================== USER MANAGEMENT ====================

@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    sort: str = Query("name"),
    order: str = Query("asc"),
    search: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    team_id: Optional[int] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List users with pagination, filtering, and sorting"""
    # Base query
    query = select(User).options(selectinload(User.team))

    # Team admin can only see users from their team
    if not current_user.is_super_admin and current_user.team_id:
        query = query.where(User.team_id == current_user.team_id)

    # Filters
    if search:
        query = query.where(
            or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )

    if role:
        try:
            role_enum = UserRole(role)
            query = query.where(User.role == role_enum)
        except ValueError:
            pass

    if status == "active":
        query = query.where(User.is_active == True)
    elif status == "inactive":
        query = query.where(User.is_active == False)

    if team_id:
        query = query.where(User.team_id == team_id)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Sorting
    sort_column = getattr(User, sort, User.name)
    if order == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Pagination
    query = query.offset((page - 1) * limit).limit(limit)

    result = await db.execute(query)
    users = result.scalars().all()

    return UserListResponse(
        users=[
            UserResponse(
                id=u.id,
                email=u.email,
                name=u.name,
                role=u.role.value,
                team_id=u.team_id,
                team_name=u.team.name if u.team else None,
                is_active=u.is_active,
                created_at=u.created_at,
                last_login=u.last_login
            )
            for u in users
        ],
        total=total
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get user by ID"""
    result = await db.execute(
        select(User).options(selectinload(User.team)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Permission check
    if not current_user.is_super_admin:
        if user.team_id != current_user.team_id:
            raise HTTPException(status_code=403, detail="Cannot access user from different team")

    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.value,
        team_id=user.team_id,
        team_name=user.team.name if user.team else None,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login
    )


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update user"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Permission check
    if not current_user.is_super_admin:
        if user.team_id != current_user.team_id:
            raise HTTPException(status_code=403, detail="Cannot update user from different team")
        # Team admin cannot change role to super_admin
        if data.role == "super_admin":
            raise HTTPException(status_code=403, detail="Cannot promote to super_admin")

    # Update fields
    if data.name is not None:
        user.name = data.name

    if data.team_id is not None:
        # Verify team exists
        team_result = await db.execute(select(Team).where(Team.id == data.team_id))
        if not team_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Team not found")
        user.team_id = data.team_id

    if data.role is not None:
        try:
            user.role = UserRole(data.role)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid role")

    if data.is_active is not None:
        user.is_active = data.is_active

    user.updated_at = datetime.utcnow()
    await db.commit()

    return {"message": "User updated successfully"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete user"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Permission check
    if not current_user.is_super_admin:
        if user.team_id != current_user.team_id:
            raise HTTPException(status_code=403, detail="Cannot delete user from different team")
        if user.role == UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="Cannot delete super_admin")

    await db.delete(user)
    await db.commit()

    return {"message": "User deleted successfully"}


# ==================== FEEDBACK ====================

@router.get("/feedback", response_model=List[FeedbackResponse])
async def list_feedback(
    status: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all feedback"""
    query = (
        select(Feedback)
        .options(selectinload(Feedback.user))
        .order_by(Feedback.created_at.desc())
    )

    if status:
        try:
            status_enum = FeedbackStatus(status)
            query = query.where(Feedback.status == status_enum)
        except ValueError:
            pass

    result = await db.execute(query)
    feedback_list = result.scalars().all()

    return [
        FeedbackResponse(
            id=fb.id,
            user_id=fb.user_id,
            user_email=fb.user.email if fb.user else "unknown",
            title=fb.title,
            content=fb.content,
            status=fb.status.value,
            created_at=fb.created_at,
            updated_at=fb.updated_at
        )
        for fb in feedback_list
    ]


@router.get("/feedback/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(
    feedback_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get feedback by ID"""
    result = await db.execute(
        select(Feedback)
        .options(selectinload(Feedback.user))
        .where(Feedback.id == feedback_id)
    )
    feedback = result.scalar_one_or_none()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    return FeedbackResponse(
        id=feedback.id,
        user_id=feedback.user_id,
        user_email=feedback.user.email if feedback.user else "unknown",
        title=feedback.title,
        content=feedback.content,
        status=feedback.status.value,
        created_at=feedback.created_at,
        updated_at=feedback.updated_at
    )


@router.post("/feedback")
async def create_feedback(
    data: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new feedback (any authenticated user)"""
    feedback = Feedback(
        user_id=current_user.id,
        title=data.title,
        content=data.content,
        status=FeedbackStatus.NEW
    )

    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    return {"id": feedback.id, "message": "Feedback submitted successfully"}


@router.put("/feedback/{feedback_id}")
async def update_feedback(
    feedback_id: int,
    data: FeedbackUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update feedback status"""
    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    feedback = result.scalar_one_or_none()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    if data.status:
        try:
            new_status = FeedbackStatus(data.status)
            feedback.status = new_status

            if new_status == FeedbackStatus.RESOLVED:
                feedback.resolved_at = datetime.utcnow()
                feedback.resolved_by = current_user.id
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")

    if data.title is not None:
        feedback.title = data.title

    feedback.updated_at = datetime.utcnow()
    await db.commit()

    return {"message": "Feedback updated successfully"}


@router.delete("/feedback/{feedback_id}")
async def delete_feedback(
    feedback_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete feedback"""
    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    feedback = result.scalar_one_or_none()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    await db.delete(feedback)
    await db.commit()

    return {"message": "Feedback deleted successfully"}
