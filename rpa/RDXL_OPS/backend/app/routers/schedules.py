"""
Schedules Router

API endpoints for managing scheduled tasks.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from ..database import get_db
from ..dependencies import get_current_user
from ..models import User
from ..models.schedule import Schedule, ScheduleType, ScheduleStatus
from ..services.scheduler_service import scheduler_service

router = APIRouter()


# Pydantic models
class ScheduleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    agent_name: str
    command: Optional[str] = None
    schedule_type: str = "cron"  # cron, interval, date
    cron_expression: Optional[str] = None  # e.g., "0 9 * * *" for 9am daily
    interval_seconds: Optional[int] = None
    interval_minutes: Optional[int] = None
    interval_hours: Optional[int] = None
    run_date: Optional[datetime] = None


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    command: Optional[str] = None
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    interval_minutes: Optional[int] = None
    interval_hours: Optional[int] = None
    is_enabled: Optional[bool] = None


class ScheduleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    agent_name: str
    command: Optional[str]
    schedule_type: str
    cron_expression: Optional[str]
    status: str
    is_enabled: bool
    last_run: Optional[str]
    next_run: Optional[str]
    run_count: int
    created_at: str

    class Config:
        from_attributes = True


@router.get("/schedules", response_model=List[ScheduleResponse])
async def list_schedules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all schedules.

    Super admins see all schedules.
    Team admins see their team's schedules.
    """
    query = select(Schedule)

    # Filter by team for non-super admins
    if current_user.role.value != "super_admin":
        if current_user.team_id:
            query = query.where(Schedule.team_id == current_user.team_id)
        else:
            query = query.where(Schedule.created_by == current_user.id)

    result = await db.execute(query.order_by(Schedule.created_at.desc()))
    schedules = result.scalars().all()

    return [
        ScheduleResponse(
            id=s.id,
            name=s.name,
            description=s.description,
            agent_name=s.agent_name,
            command=s.command,
            schedule_type=s.schedule_type.value,
            cron_expression=s.cron_expression,
            status=s.status.value,
            is_enabled=s.is_enabled,
            last_run=s.last_run.isoformat() if s.last_run else None,
            next_run=scheduler_service.get_next_run_time(s.id).isoformat()
                if scheduler_service.get_next_run_time(s.id) else None,
            run_count=s.run_count,
            created_at=s.created_at.isoformat() if s.created_at else None
        )
        for s in schedules
    ]


@router.post("/schedules", response_model=ScheduleResponse)
async def create_schedule(
    data: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new schedule.

    Only team_admin and super_admin can create schedules.
    """
    if current_user.role.value not in ["super_admin", "team_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create schedules"
        )

    # Validate schedule type
    try:
        schedule_type = ScheduleType(data.schedule_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid schedule type. Must be one of: cron, interval, date"
        )

    # Validate required fields based on type
    if schedule_type == ScheduleType.CRON and not data.cron_expression:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cron_expression is required for cron schedules"
        )

    if schedule_type == ScheduleType.INTERVAL:
        if not any([data.interval_seconds, data.interval_minutes, data.interval_hours]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one interval value is required for interval schedules"
            )

    if schedule_type == ScheduleType.DATE and not data.run_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="run_date is required for date schedules"
        )

    # Create schedule
    schedule = Schedule(
        name=data.name,
        description=data.description,
        agent_name=data.agent_name,
        command=data.command,
        schedule_type=schedule_type,
        cron_expression=data.cron_expression,
        interval_seconds=data.interval_seconds,
        interval_minutes=data.interval_minutes,
        interval_hours=data.interval_hours,
        run_date=data.run_date,
        created_by=current_user.id,
        team_id=current_user.team_id
    )

    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)

    # Add to scheduler
    try:
        scheduler_service.add_schedule(schedule)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid schedule configuration: {str(e)}"
        )

    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=schedule.description,
        agent_name=schedule.agent_name,
        command=schedule.command,
        schedule_type=schedule.schedule_type.value,
        cron_expression=schedule.cron_expression,
        status=schedule.status.value,
        is_enabled=schedule.is_enabled,
        last_run=None,
        next_run=scheduler_service.get_next_run_time(schedule.id).isoformat()
            if scheduler_service.get_next_run_time(schedule.id) else None,
        run_count=0,
        created_at=schedule.created_at.isoformat()
    )


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific schedule."""
    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=schedule.description,
        agent_name=schedule.agent_name,
        command=schedule.command,
        schedule_type=schedule.schedule_type.value,
        cron_expression=schedule.cron_expression,
        status=schedule.status.value,
        is_enabled=schedule.is_enabled,
        last_run=schedule.last_run.isoformat() if schedule.last_run else None,
        next_run=scheduler_service.get_next_run_time(schedule.id).isoformat()
            if scheduler_service.get_next_run_time(schedule.id) else None,
        run_count=schedule.run_count,
        created_at=schedule.created_at.isoformat() if schedule.created_at else None
    )


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a schedule."""
    if current_user.role.value not in ["super_admin", "team_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update schedules"
        )

    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    # Update fields
    if data.name is not None:
        schedule.name = data.name
    if data.description is not None:
        schedule.description = data.description
    if data.command is not None:
        schedule.command = data.command
    if data.cron_expression is not None:
        schedule.cron_expression = data.cron_expression
    if data.interval_seconds is not None:
        schedule.interval_seconds = data.interval_seconds
    if data.interval_minutes is not None:
        schedule.interval_minutes = data.interval_minutes
    if data.interval_hours is not None:
        schedule.interval_hours = data.interval_hours
    if data.is_enabled is not None:
        schedule.is_enabled = data.is_enabled
        if data.is_enabled:
            scheduler_service.resume_schedule(schedule_id)
        else:
            scheduler_service.pause_schedule(schedule_id)

    await db.commit()
    await db.refresh(schedule)

    # Re-add to scheduler if configuration changed
    if any([data.cron_expression, data.interval_seconds, data.interval_minutes, data.interval_hours]):
        scheduler_service.remove_schedule(schedule_id)
        scheduler_service.add_schedule(schedule)

    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=schedule.description,
        agent_name=schedule.agent_name,
        command=schedule.command,
        schedule_type=schedule.schedule_type.value,
        cron_expression=schedule.cron_expression,
        status=schedule.status.value,
        is_enabled=schedule.is_enabled,
        last_run=schedule.last_run.isoformat() if schedule.last_run else None,
        next_run=scheduler_service.get_next_run_time(schedule.id).isoformat()
            if scheduler_service.get_next_run_time(schedule.id) else None,
        run_count=schedule.run_count,
        created_at=schedule.created_at.isoformat() if schedule.created_at else None
    )


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a schedule."""
    if current_user.role.value not in ["super_admin", "team_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete schedules"
        )

    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    # Remove from scheduler
    scheduler_service.remove_schedule(schedule_id)

    # Delete from database
    await db.delete(schedule)
    await db.commit()

    return {"success": True, "message": "Schedule deleted"}


@router.post("/schedules/{schedule_id}/run")
async def run_schedule_now(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Run a schedule immediately (manual trigger).
    """
    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )

    # Import here to avoid circular import
    from agents.registry import agent_registry

    # Execute the agent
    exec_result = await agent_registry.run_agent(schedule.agent_name, schedule.command)

    # Update schedule stats
    schedule.last_run = datetime.utcnow()
    schedule.run_count += 1
    schedule.last_result = str(exec_result)
    await db.commit()

    return {
        "success": True,
        "schedule_id": schedule_id,
        "result": exec_result
    }


@router.get("/scheduler/status")
async def get_scheduler_status(
    current_user: User = Depends(get_current_user)
):
    """Get scheduler status and job list."""
    return {
        "is_running": scheduler_service.is_running,
        "jobs": scheduler_service.list_jobs()
    }
