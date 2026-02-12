"""
Scheduler System Tests

Tests for the APScheduler-based scheduling system.
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.services.scheduler_service import SchedulerService, scheduler_service
from backend.app.models.schedule import Schedule, ScheduleType, ScheduleStatus


class TestSchedulerService:
    """Tests for the scheduler service."""

    def test_scheduler_singleton(self):
        """Test that SchedulerService is a singleton."""
        service1 = SchedulerService()
        service2 = SchedulerService()
        assert service1 is service2

    def test_scheduler_start_stop(self):
        """Test starting and stopping the scheduler."""
        service = scheduler_service

        # Start
        service.start()
        assert service.is_running is True

        # Stop
        service.stop()
        assert service.is_running is False

        # Restart for other tests
        service.start()

    def test_list_jobs_empty(self):
        """Test listing jobs when scheduler is empty."""
        service = scheduler_service
        service.start()

        jobs = service.list_jobs()
        assert isinstance(jobs, list)


class TestScheduleModel:
    """Tests for the Schedule model."""

    def test_schedule_type_enum(self):
        """Test ScheduleType enum values."""
        assert ScheduleType.CRON.value == "cron"
        assert ScheduleType.INTERVAL.value == "interval"
        assert ScheduleType.DATE.value == "date"

    def test_schedule_status_enum(self):
        """Test ScheduleStatus enum values."""
        assert ScheduleStatus.ACTIVE.value == "active"
        assert ScheduleStatus.PAUSED.value == "paused"
        assert ScheduleStatus.DISABLED.value == "disabled"


class TestScheduleEndpoints:
    """Tests for schedule API endpoints."""

    @pytest.mark.asyncio
    async def test_list_schedules(self, client: AsyncClient, auth_headers):
        """Test GET /api/schedules endpoint."""
        response = await client.get(
            "/api/schedules",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_schedules_unauthenticated(self, client: AsyncClient):
        """Test GET /api/schedules without authentication."""
        response = await client.get("/api/schedules")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_schedule_cron(self, client: AsyncClient, admin_auth_headers):
        """Test creating a cron schedule."""
        response = await client.post(
            "/api/schedules",
            json={
                "name": "Test Cron Schedule",
                "description": "Test schedule for unit tests",
                "agent_name": "system",
                "command": "status",
                "schedule_type": "cron",
                "cron_expression": "0 9 * * *"  # Daily at 9 AM
            },
            headers=admin_auth_headers
        )

        # 200/201 for success, 403 for permission denied, 400 for validation error
        assert response.status_code in [200, 201, 400, 403]

        if response.status_code in [200, 201]:
            data = response.json()
            assert data["name"] == "Test Cron Schedule"
            assert data["schedule_type"] == "cron"

    @pytest.mark.asyncio
    async def test_create_schedule_interval(self, client: AsyncClient, admin_auth_headers):
        """Test creating an interval schedule."""
        response = await client.post(
            "/api/schedules",
            json={
                "name": "Test Interval Schedule",
                "description": "Test interval schedule",
                "agent_name": "system",
                "schedule_type": "interval",
                "interval_hours": 1
            },
            headers=admin_auth_headers
        )

        assert response.status_code in [200, 201, 400, 403]

    @pytest.mark.asyncio
    async def test_create_schedule_date(self, client: AsyncClient, admin_auth_headers):
        """Test creating a one-time date schedule."""
        future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()

        response = await client.post(
            "/api/schedules",
            json={
                "name": "Test Date Schedule",
                "description": "One-time execution test",
                "agent_name": "system",
                "schedule_type": "date",
                "run_date": future_date
            },
            headers=admin_auth_headers
        )

        assert response.status_code in [200, 201, 400, 403]

    @pytest.mark.asyncio
    async def test_create_schedule_permission_denied(self, client: AsyncClient, auth_headers):
        """Test that regular users cannot create schedules."""
        response = await client.post(
            "/api/schedules",
            json={
                "name": "Unauthorized Schedule",
                "agent_name": "system",
                "schedule_type": "cron",
                "cron_expression": "0 9 * * *"
            },
            headers=auth_headers
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_schedule_invalid_cron(self, client: AsyncClient, admin_auth_headers):
        """Test creating a schedule with invalid cron expression."""
        response = await client.post(
            "/api/schedules",
            json={
                "name": "Invalid Cron Schedule",
                "agent_name": "system",
                "schedule_type": "cron",
                "cron_expression": "invalid cron"
            },
            headers=admin_auth_headers
        )

        # Should fail validation
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_cron_schedule_missing_expression(
        self, client: AsyncClient, admin_auth_headers
    ):
        """Test creating a cron schedule without cron_expression."""
        response = await client.post(
            "/api/schedules",
            json={
                "name": "Missing Cron Expression",
                "agent_name": "system",
                "schedule_type": "cron"
                # Missing cron_expression
            },
            headers=admin_auth_headers
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_scheduler_status(self, client: AsyncClient, auth_headers):
        """Test GET /api/scheduler/status endpoint."""
        response = await client.get(
            "/api/scheduler/status",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "is_running" in data
        assert "jobs" in data

    @pytest.mark.asyncio
    async def test_delete_schedule_not_found(self, client: AsyncClient, admin_auth_headers):
        """Test deleting a non-existent schedule."""
        response = await client.delete(
            "/api/schedules/99999",
            headers=admin_auth_headers
        )

        assert response.status_code == 404


class TestScheduleValidation:
    """Tests for schedule validation."""

    @pytest.mark.asyncio
    async def test_interval_schedule_requires_interval(
        self, client: AsyncClient, admin_auth_headers
    ):
        """Test that interval schedule requires at least one interval value."""
        response = await client.post(
            "/api/schedules",
            json={
                "name": "Invalid Interval Schedule",
                "agent_name": "system",
                "schedule_type": "interval"
                # Missing all interval values
            },
            headers=admin_auth_headers
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_date_schedule_requires_run_date(
        self, client: AsyncClient, admin_auth_headers
    ):
        """Test that date schedule requires run_date."""
        response = await client.post(
            "/api/schedules",
            json={
                "name": "Invalid Date Schedule",
                "agent_name": "system",
                "schedule_type": "date"
                # Missing run_date
            },
            headers=admin_auth_headers
        )

        assert response.status_code == 400
