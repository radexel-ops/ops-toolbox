"""
Knowledge Router

Handles knowledge documents and guidelines access.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from ..database import get_db
from ..models import Team, User, UserRole
from ..services.knowledge_service import knowledge_service
from ..dependencies import get_current_user, get_super_admin

router = APIRouter()


# ==================== Master Knowledge ====================

@router.get("/master/guideline")
async def get_master_guideline(
    current_user: User = Depends(get_current_user)
):
    """Get master CLAUDE.md content (read-only for all authenticated users)"""
    content = knowledge_service.get_master_guideline()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Master guideline not found"
        )

    return {
        "path": "CLAUDE.md",
        "content": content,
        "can_edit": current_user.can_edit_master_guidelines()
    }


@router.put("/master/guideline")
async def update_master_guideline(
    content: str,
    current_user: User = Depends(get_super_admin)
):
    """Update master CLAUDE.md (super admin only)"""
    success = knowledge_service.update_master_guideline(content, current_user)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update master guideline"
        )

    return {
        "success": True,
        "message": "Master guideline updated successfully"
    }


@router.get("/master/knowledge")
async def list_master_knowledge(
    current_user: User = Depends(get_current_user)
):
    """List all master knowledge documents"""
    files = knowledge_service.get_master_knowledge_list()

    return {
        "path": "knowledge/",
        "files": files,
        "count": len(files)
    }


@router.get("/master/knowledge/{filename}")
async def get_master_knowledge_file(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """Get specific master knowledge document"""
    content = knowledge_service.get_master_knowledge(filename)

    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge file '{filename}' not found"
        )

    return {
        "path": f"knowledge/{filename}",
        "content": content
    }


# ==================== Team Knowledge ====================

@router.get("/team/{team_slug}/guideline")
async def get_team_guideline(
    team_slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get team's TEAM_CLAUDE.md content"""
    # Get team
    result = await db.execute(
        select(Team).where(Team.slug == team_slug)
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Check access
    if not current_user.can_access_team(team.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this team"
        )

    content = knowledge_service.get_team_guideline(team_slug)

    return {
        "team_slug": team_slug,
        "team_name": team.name,
        "path": knowledge_service.get_team_guideline_path(team_slug),
        "content": content or "",
        "can_edit": current_user.can_edit_team_guidelines(team.id)
    }


@router.put("/team/{team_slug}/guideline")
async def update_team_guideline(
    team_slug: str,
    content: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update team's TEAM_CLAUDE.md"""
    # Get team
    result = await db.execute(
        select(Team).where(Team.slug == team_slug)
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Check edit permission
    if not current_user.can_edit_team_guidelines(team.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to edit this team's guidelines"
        )

    success = knowledge_service.update_team_guideline(
        team_slug, content, current_user, team.id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update team guideline"
        )

    # Sync to database
    await knowledge_service.sync_team_guideline_to_db(db, team)

    return {
        "success": True,
        "message": f"Team {team_slug} guideline updated successfully"
    }


@router.get("/team/{team_slug}/knowledge")
async def list_team_knowledge(
    team_slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all team knowledge documents"""
    # Get team
    result = await db.execute(
        select(Team).where(Team.slug == team_slug)
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Check access
    if not current_user.can_access_team(team.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this team"
        )

    files = knowledge_service.get_team_knowledge_list(team_slug)

    return {
        "team_slug": team_slug,
        "path": knowledge_service.get_team_knowledge_path(team_slug),
        "files": files,
        "count": len(files)
    }


# ==================== Merged Context ====================

@router.get("/context/{team_slug}")
async def get_team_context(
    team_slug: str,
    include_master_knowledge: bool = False,
    include_team_knowledge: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get complete team context for AI.

    Returns merged guidelines and available knowledge files.
    """
    # Get team
    result = await db.execute(
        select(Team).where(Team.slug == team_slug)
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Check access
    if not current_user.can_access_team(team.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this team"
        )

    context = knowledge_service.get_team_context(team_slug)

    # Optionally include expanded guidelines
    if include_master_knowledge or include_team_knowledge:
        context["guidelines"] = knowledge_service.get_merged_guidelines(
            team_slug,
            include_master_knowledge=include_master_knowledge,
            include_team_knowledge=include_team_knowledge
        )

    return context


@router.get("/merged/{team_slug}")
async def get_merged_guidelines(
    team_slug: str,
    include_master_knowledge: bool = False,
    include_team_knowledge: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get merged guidelines for AI prompt.

    Master + Team guidelines combined.
    """
    # Get team
    result = await db.execute(
        select(Team).where(Team.slug == team_slug)
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Check access
    if not current_user.can_access_team(team.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this team"
        )

    merged = knowledge_service.get_merged_guidelines(
        team_slug,
        include_master_knowledge=include_master_knowledge,
        include_team_knowledge=include_team_knowledge
    )

    return {
        "team_slug": team_slug,
        "team_name": team.name,
        "merged_guidelines": merged,
        "includes_master_knowledge": include_master_knowledge,
        "includes_team_knowledge": include_team_knowledge
    }
