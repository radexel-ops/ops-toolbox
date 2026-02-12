"""
VibeOps Test Configuration

Pytest fixtures for testing the VibeOps application.
"""

import pytest
import pytest_asyncio
import asyncio
import os
import sys
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.app.main import app
from backend.app.database import Base, get_db
from backend.app.models import User, UserRole, Team


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session_maker = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async test client with database session override.
    """
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_team(test_session: AsyncSession) -> Team:
    """Create a test team."""
    team = Team(
        name="test_team",
        display_name="Test Team",
        description="Test team for unit tests"
    )
    test_session.add(team)
    await test_session.commit()
    await test_session.refresh(team)
    return team


@pytest_asyncio.fixture(scope="function")
async def test_user(test_session: AsyncSession, test_team: Team) -> User:
    """Create a test user."""
    from backend.app.services.auth_service import get_password_hash

    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=get_password_hash("TestPassword123!"),
        full_name="Test User",
        team_id=test_team.id,
        role=UserRole.USER,
        is_active=True
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_admin(test_session: AsyncSession, test_team: Team) -> User:
    """Create a test admin user."""
    from backend.app.services.auth_service import get_password_hash

    admin = User(
        username="testadmin",
        email="admin@example.com",
        password_hash=get_password_hash("AdminPassword123!"),
        full_name="Test Admin",
        team_id=test_team.id,
        role=UserRole.TEAM_ADMIN,
        is_active=True
    )
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)
    return admin


@pytest_asyncio.fixture(scope="function")
async def test_super_admin(test_session: AsyncSession) -> User:
    """Create a test super admin user."""
    from backend.app.services.auth_service import get_password_hash

    super_admin = User(
        username="superadmin",
        email="superadmin@example.com",
        password_hash=get_password_hash("SuperAdminPassword123!"),
        full_name="Super Admin",
        team_id=None,
        role=UserRole.SUPER_ADMIN,
        is_active=True
    )
    test_session.add(super_admin)
    await test_session.commit()
    await test_session.refresh(super_admin)
    return super_admin


@pytest_asyncio.fixture(scope="function")
async def auth_headers(client: AsyncClient, test_user: User) -> dict:
    """Get authentication headers for test user."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "TestPassword123!"}
    )
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def admin_auth_headers(client: AsyncClient, test_admin: User) -> dict:
    """Get authentication headers for admin user."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "testadmin", "password": "AdminPassword123!"}
    )
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def super_admin_auth_headers(client: AsyncClient, test_super_admin: User) -> dict:
    """Get authentication headers for super admin user."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "superadmin", "password": "SuperAdminPassword123!"}
    )
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}
