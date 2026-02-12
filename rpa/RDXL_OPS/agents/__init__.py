"""
VibeOps Agents

Automation agents for various tasks.
"""

from .registry import agent_registry, register_agent
from .base.agent_base import AgentBase

# Import agent implementations to register them
from .implementations import PMAgent, NewsAgent, SystemAgent

# Import douzone agents
try:
    from .douzone import VacationAgent
except ImportError:
    VacationAgent = None  # Selenium may not be installed

__all__ = [
    "agent_registry",
    "register_agent",
    "AgentBase",
    # Implementations
    "PMAgent",
    "NewsAgent",
    "SystemAgent",
    "VacationAgent",
]
