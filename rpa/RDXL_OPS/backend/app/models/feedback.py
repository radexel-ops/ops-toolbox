"""
Feedback Model

Represents user feedback for admin management.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from ..database import Base


class FeedbackStatus(str, enum.Enum):
    """Feedback status values"""
    NEW = "new"
    REVIEWING = "reviewing"
    RESOLVED = "resolved"


class Feedback(Base):
    """
    User feedback entity.

    Stores user-submitted feedback for admin review and management.
    """
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    status = Column(Enum(FeedbackStatus), default=FeedbackStatus.NEW, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="feedback_submitted")
    resolver = relationship("User", foreign_keys=[resolved_by])

    def __repr__(self):
        return f"<Feedback(id={self.id}, status='{self.status}')>"
