"""
Authentication Service

Handles user authentication, JWT token management, and session management.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import secrets

from ..config import settings
from ..models import User, Session, Team, UserRole

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service for authentication operations"""

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(
        user: User,
        team: Optional[Team] = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token.

        Payload includes:
        - sub: user_id
        - email: user email
        - role: user role
        - team_id: user's team ID (if applicable)
        - team_slug: team slug for easy lookup
        """
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "team_id": user.team_id,
            "team_slug": team.slug if team else None,
            "exp": expire,
            "iat": datetime.utcnow(),
        }

        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def create_refresh_token() -> str:
        """Create a random refresh token"""
        return secrets.token_urlsafe(64)

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """Decode and validate JWT token"""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            return payload
        except JWTError:
            return None

    async def authenticate_user(
        self,
        db: AsyncSession,
        email: str,
        password: str
    ) -> Optional[User]:
        """
        Authenticate user by email and password.

        Returns User if valid, None otherwise.
        """
        result = await db.execute(
            select(User).where(User.email == email, User.is_active == True)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        if not self.verify_password(password, user.password_hash):
            return None

        return user

    async def login(
        self,
        db: AsyncSession,
        email: str,
        password: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Optional[Tuple[str, str, User]]:
        """
        Perform login and create tokens.

        Returns (access_token, refresh_token, user) or None if invalid.
        """
        user = await self.authenticate_user(db, email, password)
        if not user:
            return None

        # Get team info
        team = None
        if user.team_id:
            result = await db.execute(
                select(Team).where(Team.id == user.team_id)
            )
            team = result.scalar_one_or_none()

        # Create tokens
        access_token = self.create_access_token(user, team)
        refresh_token = self.create_refresh_token()

        # Create session
        session = Session(
            user_id=user.id,
            refresh_token=refresh_token,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        db.add(session)

        # Update last login
        user.last_login = datetime.utcnow()

        await db.commit()

        return access_token, refresh_token, user

    async def refresh_tokens(
        self,
        db: AsyncSession,
        refresh_token: str
    ) -> Optional[Tuple[str, str]]:
        """
        Refresh access token using refresh token.

        Returns (new_access_token, new_refresh_token) or None if invalid.
        """
        # Find session
        result = await db.execute(
            select(Session).where(
                Session.refresh_token == refresh_token,
                Session.is_revoked == False
            )
        )
        session = result.scalar_one_or_none()

        if not session or not session.is_valid:
            return None

        # Get user
        result = await db.execute(
            select(User).where(User.id == session.user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        # Get team
        team = None
        if user.team_id:
            result = await db.execute(
                select(Team).where(Team.id == user.team_id)
            )
            team = result.scalar_one_or_none()

        # Revoke old session
        session.is_revoked = True

        # Create new tokens and session
        new_access_token = self.create_access_token(user, team)
        new_refresh_token = self.create_refresh_token()

        new_session = Session(
            user_id=user.id,
            refresh_token=new_refresh_token,
            user_agent=session.user_agent,
            ip_address=session.ip_address,
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        db.add(new_session)

        await db.commit()

        return new_access_token, new_refresh_token

    async def logout(self, db: AsyncSession, refresh_token: str) -> bool:
        """
        Logout by revoking refresh token.

        Returns True if successful.
        """
        result = await db.execute(
            select(Session).where(Session.refresh_token == refresh_token)
        )
        session = result.scalar_one_or_none()

        if session:
            session.is_revoked = True
            await db.commit()
            return True

        return False

    async def logout_all(self, db: AsyncSession, user_id: int) -> int:
        """
        Logout from all sessions.

        Returns number of revoked sessions.
        """
        result = await db.execute(
            select(Session).where(
                Session.user_id == user_id,
                Session.is_revoked == False
            )
        )
        sessions = result.scalars().all()

        count = 0
        for session in sessions:
            session.is_revoked = True
            count += 1

        await db.commit()
        return count

    async def get_user_by_id(self, db: AsyncSession, user_id: int) -> Optional[User]:
        """Get user by ID with team relationship loaded"""
        result = await db.execute(
            select(User).options(selectinload(User.team)).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def change_password(
        self,
        db: AsyncSession,
        user: User,
        current_password: str,
        new_password: str
    ) -> bool:
        """
        Change user password.

        Returns True if successful.
        """
        if not self.verify_password(current_password, user.password_hash):
            return False

        user.password_hash = self.hash_password(new_password)
        await db.commit()
        return True


# Global service instance
auth_service = AuthService()
