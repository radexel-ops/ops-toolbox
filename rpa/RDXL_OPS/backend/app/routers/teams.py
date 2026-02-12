"""
Teams Router

Handles team management, team access, and team guidelines.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from ..database import get_db
from ..models import Team, User, TeamGuideline, UserRole
from ..schemas.team import (
    TeamCreate, TeamUpdate, TeamResponse, TeamListResponse,
    TeamGuidelineResponse, TeamGuidelineUpdate
)
from ..dependencies import (
    get_current_user, get_super_admin, get_team_admin,
    TeamAccessChecker
)

router = APIRouter()


@router.get("/", response_model=TeamListResponse)
async def list_teams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all teams.

    - Super admin: sees all teams
    - Others: see only their team
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        # Get all teams with member count
        result = await db.execute(
            select(Team).where(Team.is_active == True).order_by(Team.name)
        )
        teams = result.scalars().all()
    else:
        # Get only user's team
        if not current_user.team_id:
            return TeamListResponse(total=0, teams=[])

        result = await db.execute(
            select(Team).where(Team.id == current_user.team_id)
        )
        teams = result.scalars().all()

    # Add member counts
    team_responses = []
    for team in teams:
        count_result = await db.execute(
            select(func.count(User.id)).where(User.team_id == team.id)
        )
        member_count = count_result.scalar() or 0

        team_responses.append(TeamResponse(
            id=team.id,
            slug=team.slug,
            name=team.name,
            description=team.description,
            is_active=team.is_active,
            created_at=team.created_at,
            updated_at=team.updated_at,
            member_count=member_count
        ))

    return TeamListResponse(total=len(team_responses), teams=team_responses)


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: int,
    current_user: User = Depends(TeamAccessChecker()),
    db: AsyncSession = Depends(get_db)
):
    """
    Get team details by ID.
    """
    result = await db.execute(
        select(Team).where(Team.id == team_id)
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Get member count
    count_result = await db.execute(
        select(func.count(User.id)).where(User.team_id == team.id)
    )
    member_count = count_result.scalar() or 0

    return TeamResponse(
        id=team.id,
        slug=team.slug,
        name=team.name,
        description=team.description,
        is_active=team.is_active,
        created_at=team.created_at,
        updated_at=team.updated_at,
        member_count=member_count
    )


@router.get("/slug/{slug}", response_model=TeamResponse)
async def get_team_by_slug(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get team details by slug.
    """
    result = await db.execute(
        select(Team).where(Team.slug == slug)
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Check access
    if current_user.role != UserRole.SUPER_ADMIN and current_user.team_id != team.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this team"
        )

    # Get member count
    count_result = await db.execute(
        select(func.count(User.id)).where(User.team_id == team.id)
    )
    member_count = count_result.scalar() or 0

    return TeamResponse(
        id=team.id,
        slug=team.slug,
        name=team.name,
        description=team.description,
        is_active=team.is_active,
        created_at=team.created_at,
        updated_at=team.updated_at,
        member_count=member_count
    )


@router.post("/", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    team_data: TeamCreate,
    current_user: User = Depends(get_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new team (super admin only).
    """
    # Check if slug already exists
    result = await db.execute(
        select(Team).where(Team.slug == team_data.slug)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team with slug '{team_data.slug}' already exists"
        )

    team = Team(
        slug=team_data.slug,
        name=team_data.name,
        description=team_data.description
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)

    return TeamResponse(
        id=team.id,
        slug=team.slug,
        name=team.name,
        description=team.description,
        is_active=team.is_active,
        created_at=team.created_at,
        updated_at=team.updated_at,
        member_count=0
    )


@router.patch("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: int,
    team_data: TeamUpdate,
    current_user: User = Depends(get_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update team details (super admin only).
    """
    result = await db.execute(
        select(Team).where(Team.id == team_id)
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Update fields
    if team_data.name is not None:
        team.name = team_data.name
    if team_data.description is not None:
        team.description = team_data.description
    if team_data.is_active is not None:
        team.is_active = team_data.is_active

    await db.commit()
    await db.refresh(team)

    # Get member count
    count_result = await db.execute(
        select(func.count(User.id)).where(User.team_id == team.id)
    )
    member_count = count_result.scalar() or 0

    return TeamResponse(
        id=team.id,
        slug=team.slug,
        name=team.name,
        description=team.description,
        is_active=team.is_active,
        created_at=team.created_at,
        updated_at=team.updated_at,
        member_count=member_count
    )


@router.get("/{team_id}/members", response_model=List[dict])
async def get_team_members(
    team_id: int,
    current_user: User = Depends(TeamAccessChecker()),
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of team members.
    """
    result = await db.execute(
        select(User).where(User.team_id == team_id, User.is_active == True)
    )
    members = result.scalars().all()

    return [
        {
            "id": m.id,
            "email": m.email,
            "name": m.name,
            "role": m.role.value,
            "last_login": m.last_login.isoformat() if m.last_login else None
        }
        for m in members
    ]


@router.get("/{team_id}/guidelines", response_model=TeamGuidelineResponse)
async def get_team_guidelines(
    team_id: int,
    current_user: User = Depends(TeamAccessChecker()),
    db: AsyncSession = Depends(get_db)
):
    """
    Get team's main guideline (TEAM_CLAUDE.md).
    """
    result = await db.execute(
        select(TeamGuideline).where(
            TeamGuideline.team_id == team_id,
            TeamGuideline.is_main_guideline == True
        )
    )
    guideline = result.scalar_one_or_none()

    if not guideline:
        # Return empty guideline if not exists
        return TeamGuidelineResponse(
            id=0,
            team_id=team_id,
            file_path=f"teams/team_{team_id}/TEAM_CLAUDE.md",
            content="",
            is_main_guideline=True,
            updated_at=None,
            updated_by=None
        )

    return TeamGuidelineResponse(
        id=guideline.id,
        team_id=guideline.team_id,
        file_path=guideline.file_path,
        content=guideline.content,
        is_main_guideline=guideline.is_main_guideline,
        updated_at=guideline.updated_at,
        updated_by=guideline.updated_by
    )


@router.put("/{team_id}/guidelines", response_model=TeamGuidelineResponse)
async def update_team_guidelines(
    team_id: int,
    guideline_data: TeamGuidelineUpdate,
    current_user: User = Depends(TeamAccessChecker(require_admin=True)),
    db: AsyncSession = Depends(get_db)
):
    """
    Update team's main guideline (team admin or super admin only).
    """
    # Get team info
    team_result = await db.execute(
        select(Team).where(Team.id == team_id)
    )
    team = team_result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Find or create guideline
    result = await db.execute(
        select(TeamGuideline).where(
            TeamGuideline.team_id == team_id,
            TeamGuideline.is_main_guideline == True
        )
    )
    guideline = result.scalar_one_or_none()

    if guideline:
        guideline.content = guideline_data.content
        guideline.updated_by = current_user.id
    else:
        guideline = TeamGuideline(
            team_id=team_id,
            file_path=f"teams/{team.slug}/TEAM_CLAUDE.md",
            content=guideline_data.content,
            is_main_guideline=True,
            updated_by=current_user.id
        )
        db.add(guideline)

    await db.commit()
    await db.refresh(guideline)

    return TeamGuidelineResponse(
        id=guideline.id,
        team_id=guideline.team_id,
        file_path=guideline.file_path,
        content=guideline.content,
        is_main_guideline=guideline.is_main_guideline,
        updated_at=guideline.updated_at,
        updated_by=guideline.updated_by
    )
