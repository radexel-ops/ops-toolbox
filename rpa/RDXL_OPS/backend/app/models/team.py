"""
Team Model

Represents organizational teams in the multi-tenant architecture.
Each team has its own isolated workspace with custom guidelines and data.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from ..database import Base


class Team(Base):
    """
    Team entity representing an organizational unit.

    Each team has:
    - Isolated directory (teams/{slug}/)
    - Custom TEAM_CLAUDE.md guidelines
    - Own knowledge documents
    - Dedicated data storage
    """
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="team")
    guidelines = relationship("TeamGuideline", back_populates="team")

    def __repr__(self):
        return f"<Team(id={self.id}, slug='{self.slug}', name='{self.name}')>"

    @property
    def directory_path(self) -> str:
        """Returns the team's isolated directory path"""
        return f"teams/{self.slug}"

    @property
    def guidelines_path(self) -> str:
        """Returns the path to team's TEAM_CLAUDE.md"""
        return f"{self.directory_path}/TEAM_CLAUDE.md"

    @property
    def knowledge_path(self) -> str:
        """Returns the path to team's knowledge directory"""
        return f"{self.directory_path}/knowledge"


class TeamGuideline(Base):
    """
    Stores team-specific guidelines and knowledge documents.

    This enables version tracking and quick access without
    filesystem reads during AI interactions.
    """
    __tablename__ = "team_guidelines"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    file_path = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    is_main_guideline = Column(Boolean, default=False)  # True for TEAM_CLAUDE.md
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, nullable=True)  # User ID who last updated

    # Relationships
    team = relationship("Team", back_populates="guidelines")

    def __repr__(self):
        return f"<TeamGuideline(team_id={self.team_id}, path='{self.file_path}')>"
