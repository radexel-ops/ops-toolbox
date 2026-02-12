"""
Agent Base Class

All agents must inherit from this base class.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Any
import logging


class AgentBase(ABC):
    """
    Base class for all VibeOps agents.

    All agents must implement:
    - execute(): Main task execution
    - health_check(): Status verification
    """

    def __init__(self, name: str, config: dict = None):
        """
        Initialize agent.

        Args:
            name: Unique agent name
            config: Optional configuration dictionary
        """
        self.name = name
        self.config = config or {}
        self.status = "initialized"
        self.last_run: Optional[datetime] = None
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Setup agent-specific logger."""
        logger = logging.getLogger(f"agent.{self.name}")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                f"%(asctime)s - [AGENT:{self.name}] - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    @abstractmethod
    async def execute(self, command: str = None) -> dict:
        """
        Execute the agent's main task.

        Args:
            command: Optional command string

        Returns:
            Execution result dictionary
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check agent health status.

        Returns:
            True if healthy, False otherwise
        """
        pass

    async def start(self):
        """Start the agent."""
        self.status = "running"
        self.logger.info(f"Agent started")

    async def stop(self):
        """Stop the agent."""
        self.status = "stopped"
        self.logger.info(f"Agent stopped")

    async def run(self, command: str = None) -> dict:
        """
        Run the agent with error handling and logging.

        Args:
            command: Optional command string

        Returns:
            Execution result with metadata
        """
        start_time = datetime.now()
        self.logger.info(f"Executing: {command or 'default task'}")

        try:
            result = await self.execute(command)
            self.last_run = datetime.now()
            duration = datetime.now() - start_time

            self.logger.info(f"Completed in {duration}")

            return {
                "status": "success",
                "result": result,
                "duration": str(duration),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Error: {str(e)}", exc_info=True)
            duration = datetime.now() - start_time

            return {
                "status": "error",
                "error": str(e),
                "duration": str(duration),
                "timestamp": datetime.now().isoformat()
            }

    def get_status(self) -> dict:
        """Get current agent status."""
        return {
            "name": self.name,
            "status": self.status,
            "last_run": self.last_run.isoformat() if self.last_run else None
        }
