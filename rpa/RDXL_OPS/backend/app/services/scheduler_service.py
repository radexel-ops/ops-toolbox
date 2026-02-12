"""
Scheduler Service

APScheduler-based task scheduling service.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Optional, List
import logging
import json
import sys
import os

# Add project root for agent imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from agents.registry import agent_registry
from ..models.schedule import Schedule, ScheduleType, ScheduleStatus

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Scheduler service for managing scheduled agent executions.

    Features:
    - Cron-based scheduling
    - Interval-based scheduling
    - One-time scheduled execution
    - Integration with agent registry
    - Persistence to database
    """

    _instance: Optional["SchedulerService"] = None
    _scheduler: Optional[AsyncIOScheduler] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._setup_scheduler()
            self._initialized = True

    def _setup_scheduler(self):
        """Configure the APScheduler instance."""
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': AsyncIOExecutor()
        }
        job_defaults = {
            'coalesce': True,  # Combine missed runs into one
            'max_instances': 1,  # Only one instance per job at a time
            'misfire_grace_time': 60  # Allow 60 seconds grace period
        }

        self._scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='Asia/Seoul'
        )

    def start(self):
        """Start the scheduler."""
        if self._scheduler and not self._scheduler.running:
            self._scheduler.start()
            logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("Scheduler stopped")

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._scheduler.running if self._scheduler else False

    async def _execute_agent_job(self, schedule_id: int, agent_name: str, command: str = None):
        """
        Execute an agent job.

        This is called by APScheduler when a job triggers.
        """
        logger.info(f"Executing scheduled job: {schedule_id} -> {agent_name}")

        try:
            result = await agent_registry.run_agent(agent_name, command)

            logger.info(f"Job {schedule_id} completed: {result.get('status')}")

            # Note: In production, update the database with results
            # This would need a database session context

            return result

        except Exception as e:
            logger.error(f"Job {schedule_id} failed: {e}")
            return {"status": "error", "error": str(e)}

    def add_schedule(self, schedule: Schedule) -> str:
        """
        Add a schedule to the scheduler.

        Args:
            schedule: Schedule model instance

        Returns:
            APScheduler job ID
        """
        job_id = f"schedule_{schedule.id}"

        # Build trigger based on schedule type
        if schedule.schedule_type == ScheduleType.CRON:
            trigger = CronTrigger.from_crontab(schedule.cron_expression)
        elif schedule.schedule_type == ScheduleType.INTERVAL:
            trigger = IntervalTrigger(
                seconds=schedule.interval_seconds or 0,
                minutes=schedule.interval_minutes or 0,
                hours=schedule.interval_hours or 0
            )
        elif schedule.schedule_type == ScheduleType.DATE:
            trigger = DateTrigger(run_date=schedule.run_date)
        else:
            raise ValueError(f"Unknown schedule type: {schedule.schedule_type}")

        # Add job to scheduler
        job = self._scheduler.add_job(
            self._execute_agent_job,
            trigger=trigger,
            id=job_id,
            name=schedule.name,
            args=[schedule.id, schedule.agent_name, schedule.command],
            replace_existing=True
        )

        logger.info(f"Added schedule {schedule.name} (job_id: {job_id})")
        return job_id

    def remove_schedule(self, schedule_id: int) -> bool:
        """
        Remove a schedule from the scheduler.

        Args:
            schedule_id: Database schedule ID

        Returns:
            True if removed, False if not found
        """
        job_id = f"schedule_{schedule_id}"
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"Removed schedule job: {job_id}")
            return True
        except Exception:
            return False

    def pause_schedule(self, schedule_id: int) -> bool:
        """Pause a schedule."""
        job_id = f"schedule_{schedule_id}"
        try:
            self._scheduler.pause_job(job_id)
            logger.info(f"Paused schedule job: {job_id}")
            return True
        except Exception:
            return False

    def resume_schedule(self, schedule_id: int) -> bool:
        """Resume a paused schedule."""
        job_id = f"schedule_{schedule_id}"
        try:
            self._scheduler.resume_job(job_id)
            logger.info(f"Resumed schedule job: {job_id}")
            return True
        except Exception:
            return False

    def get_next_run_time(self, schedule_id: int) -> Optional[datetime]:
        """Get the next run time for a schedule."""
        job_id = f"schedule_{schedule_id}"
        job = self._scheduler.get_job(job_id)
        return job.next_run_time if job else None

    def list_jobs(self) -> List[dict]:
        """List all scheduled jobs."""
        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "pending": job.pending
            })
        return jobs

    async def load_schedules_from_db(self, db: AsyncSession):
        """
        Load all active schedules from database.

        Call this on application startup.
        """
        try:
            result = await db.execute(
                select(Schedule).where(
                    Schedule.is_enabled == True,
                    Schedule.status == ScheduleStatus.ACTIVE
                )
            )
            schedules = result.scalars().all()

            for schedule in schedules:
                try:
                    self.add_schedule(schedule)
                except Exception as e:
                    logger.error(f"Failed to load schedule {schedule.id}: {e}")

            logger.info(f"Loaded {len(schedules)} schedules from database")

        except Exception as e:
            logger.error(f"Failed to load schedules: {e}")


# Global scheduler instance
scheduler_service = SchedulerService()
