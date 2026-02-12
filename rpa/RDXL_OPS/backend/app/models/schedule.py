"""
Schedule Model

Database model for storing scheduled tasks.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from ..database import Base


class ScheduleType(enum.Enum):
    """Schedule execution type."""
    CRON = "cron"      # Cron expression
    INTERVAL = "interval"  # Fixed interval
    DATE = "date"      # One-time execution


class ScheduleStatus(enum.Enum):
    """Schedule status."""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class Schedule(Base):
    """
    Scheduled task model.

    Stores information about scheduled agent executions.
    """
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)

    # Basic info
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Agent configuration
    agent_name = Column(String(100), nullable=False)
    command = Column(Text, nullable=True)  # Command to pass to agent

    # Schedule configuration
    schedule_type = Column(SQLEnum(ScheduleType), default=ScheduleType.CRON)

    # Cron expression (for CRON type)
    # Format: minute hour day_of_month month day_of_week
    cron_expression = Column(String(100), nullable=True)

    # Interval settings (for INTERVAL type)
    interval_seconds = Column(Integer, nullable=True)
    interval_minutes = Column(Integer, nullable=True)
    interval_hours = Column(Integer, nullable=True)

    # One-time execution (for DATE type)
    run_date = Column(DateTime, nullable=True)

    # Status
    status = Column(SQLEnum(ScheduleStatus), default=ScheduleStatus.ACTIVE)
    is_enabled = Column(Boolean, default=True)

    # Ownership
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)

    # Execution tracking
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    run_count = Column(Integer, default=0)
    last_result = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = relationship("User", backref="schedules")
    team = relationship("Team", backref="schedules")

    def __repr__(self):
        return f"<Schedule {self.name} ({self.agent_name})>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agent_name": self.agent_name,
            "command": self.command,
            "schedule_type": self.schedule_type.value,
            "cron_expression": self.cron_expression,
            "interval_seconds": self.interval_seconds,
            "interval_minutes": self.interval_minutes,
            "interval_hours": self.interval_hours,
            "run_date": self.run_date.isoformat() if self.run_date else None,
            "status": self.status.value,
            "is_enabled": self.is_enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
