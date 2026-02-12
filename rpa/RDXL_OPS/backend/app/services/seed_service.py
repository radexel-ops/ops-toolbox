"""
Database Seeding Service

Initializes the database with default teams and super admin user.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext

from ..models import Team, User, UserRole
from ..config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Default teams configuration
DEFAULT_TEAMS = [
    {
        "slug": "management",
        "name": "경영기획팀",
        "description": "경영 기획 및 전략 수립, AI 운영 자동화 주도"
    },
    {
        "slug": "robotics",
        "name": "로보틱스팀",
        "description": "로봇 관련 개발 및 운영"
    },
    {
        "slug": "software",
        "name": "SW팀",
        "description": "소프트웨어 개발 및 유지보수"
    },
    {
        "slug": "strategy",
        "name": "기술전략팀",
        "description": "기술 전략 및 방향 수립"
    },
    {
        "slug": "raqa",
        "name": "RA/QA팀",
        "description": "규제 대응 및 품질 관리"
    }
]


async def seed_teams(db: AsyncSession) -> list[Team]:
    """
    Create default teams if they don't exist.

    Returns list of all teams (existing + newly created).
    """
    teams = []

    for team_data in DEFAULT_TEAMS:
        # Check if team already exists
        result = await db.execute(
            select(Team).where(Team.slug == team_data["slug"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            teams.append(existing)
        else:
            team = Team(**team_data)
            db.add(team)
            teams.append(team)

    await db.commit()
    return teams


async def seed_super_admin(db: AsyncSession, email: str = "admin@vibeops.io", password: str = "admin") -> User:
    """
    Create super admin user if doesn't exist.

    Args:
        email: Super admin email
        password: Initial password (should be changed immediately)

    Returns:
        Super admin user
    """
    # Check if super admin exists
    result = await db.execute(
        select(User).where(User.email == email)
    )
    existing = result.scalar_one_or_none()

    if existing:
        return existing

    # Create super admin
    admin = User(
        email=email,
        name="System Administrator",
        password_hash=pwd_context.hash(password),
        role=UserRole.SUPER_ADMIN,
        team_id=None  # Super admin has no team
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)

    return admin


async def seed_team_admins(db: AsyncSession, teams: list[Team]) -> list[User]:
    """
    Create default team admin for each team.

    Each team gets an admin with email: {slug}@vibeops.local
    Password: {slug}admin (should be changed immediately)
    """
    admins = []

    for team in teams:
        email = f"{team.slug}@vibeops.io"

        # Check if admin exists
        result = await db.execute(
            select(User).where(User.email == email)
        )
        existing = result.scalar_one_or_none()

        if existing:
            admins.append(existing)
            continue

        # Create team admin
        admin = User(
            email=email,
            name=f"{team.name} 관리자",
            password_hash=pwd_context.hash(f"{team.slug}admin"),
            role=UserRole.TEAM_ADMIN,
            team_id=team.id
        )
        db.add(admin)
        admins.append(admin)

    await db.commit()
    return admins


async def run_all_seeds(db: AsyncSession) -> dict:
    """
    Run all seeding operations.

    Returns summary of created entities.
    """
    # Seed teams
    teams = await seed_teams(db)

    # Seed super admin
    super_admin = await seed_super_admin(db)

    # Seed team admins
    team_admins = await seed_team_admins(db, teams)

    return {
        "teams": len(teams),
        "super_admin": super_admin.email,
        "team_admins": [admin.email for admin in team_admins]
    }
