"""
Douzone (WEHAGO) Agent Module

Automation agents for Douzone WEHAGO platform.
"""

from .vacation_agent import VacationAgent
from .wehago_service import WehagoService

__all__ = [
    "VacationAgent",
    "WehagoService",
]
