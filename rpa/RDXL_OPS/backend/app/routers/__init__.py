"""
VibeOps API Routers

All API endpoint handlers.
"""

from .auth import router as auth_router
from .teams import router as teams_router
from .knowledge import router as knowledge_router
from .bridge import router as bridge_router
from .ai import router as ai_router
from .admin import router as admin_router
from .agents import router as agents_router
from .schedules import router as schedules_router

__all__ = [
    "auth_router",
    "teams_router",
    "knowledge_router",
    "bridge_router",
    "ai_router",
    "admin_router",
    "agents_router",
    "schedules_router",
]
