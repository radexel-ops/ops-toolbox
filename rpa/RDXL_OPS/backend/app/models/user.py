"""
User Model

Represents users with role-based access control for multi-tenant architecture.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from ..database import Base


class UserRole(str, enum.Enum):
    """User roles with hierarchical permissions"""
    SUPER_ADMIN = "super_admin"  # Full system access
    TEAM_ADMIN = "team_admin"    # Team management access
    MEMBER = "member"            # Standard team member


class User(Base):
    """
    User entity with role-based permissions.

    Permission hierarchy:
    - super_admin: Can modify Master guidelines, manage all teams
    - team_admin: Can modify team guidelines, manage team members
    - member: Read-only access to guidelines, can use AI chat
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.MEMBER, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)  # NULL for super_admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    team = relationship("Team", back_populates="users")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"

    @property
    def is_super_admin(self) -> bool:
        """Check if user has super admin privileges"""
        return self.role == UserRole.SUPER_ADMIN

    @property
    def is_team_admin(self) -> bool:
        """Check if user has team admin privileges"""
        return self.role in (UserRole.SUPER_ADMIN, UserRole.TEAM_ADMIN)

    def can_edit_master_guidelines(self) -> bool:
        """Check if user can edit Master CLAUDE.md and knowledge/"""
        return self.role == UserRole.SUPER_ADMIN

    def can_edit_team_guidelines(self, team_id: int) -> bool:
        """Check if user can edit specific team's guidelines"""
        if self.role == UserRole.SUPER_ADMIN:
            return True
        if self.role == UserRole.TEAM_ADMIN and self.team_id == team_id:
            return True
        return False

    def can_access_team(self, team_id: int) -> bool:
        """Check if user can access specific team's resources"""
        if self.role == UserRole.SUPER_ADMIN:
            return True
        return self.team_id == team_id


class Session(Base):
    """
    User session for JWT token management.

    Stores refresh tokens and session metadata for security.
    """
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    refresh_token = Column(String(512), unique=True, nullable=False, index=True)
    user_agent = Column(String(512), nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)

    def __repr__(self):
        return f"<Session(user_id={self.user_id}, revoked={self.is_revoked})>"

    @property
    def is_valid(self) -> bool:
        """Check if session is still valid"""
        return not self.is_revoked and self.expires_at > datetime.utcnow()
