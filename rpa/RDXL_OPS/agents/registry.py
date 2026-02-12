"""
Agent Registry

Central registry for managing all agents in the VibeOps system.
Provides discovery, registration, and lifecycle management.
"""

from typing import Dict, List, Optional, Type
from datetime import datetime
import logging
import asyncio

from .base.agent_base import AgentBase

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Singleton registry for managing all VibeOps agents.

    Features:
    - Agent registration and discovery
    - Status tracking
    - Lifecycle management (start/stop)
    - Health monitoring
    """

    _instance: Optional["AgentRegistry"] = None
    _agents: Dict[str, AgentBase] = {}
    _agent_classes: Dict[str, Type[AgentBase]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents = {}
            cls._instance._agent_classes = {}
        return cls._instance

    def register_class(self, agent_class: Type[AgentBase], name: str = None) -> None:
        """
        Register an agent class (not instance) for later instantiation.

        Args:
            agent_class: The agent class to register
            name: Optional name override (defaults to class name)
        """
        agent_name = name or agent_class.__name__
        self._agent_classes[agent_name] = agent_class
        logger.info(f"Registered agent class: {agent_name}")

    def create_agent(self, class_name: str, instance_name: str = None, config: dict = None) -> AgentBase:
        """
        Create an agent instance from a registered class.

        Args:
            class_name: Name of the registered agent class
            instance_name: Name for this instance (defaults to class_name)
            config: Configuration for the agent

        Returns:
            The created agent instance
        """
        if class_name not in self._agent_classes:
            raise ValueError(f"Agent class '{class_name}' not registered")

        agent_class = self._agent_classes[class_name]
        name = instance_name or class_name
        agent = agent_class(name=name, config=config)

        self._agents[name] = agent
        logger.info(f"Created agent instance: {name}")

        return agent

    def register(self, agent: AgentBase) -> None:
        """
        Register an existing agent instance.

        Args:
            agent: The agent instance to register
        """
        self._agents[agent.name] = agent
        logger.info(f"Registered agent instance: {agent.name}")

    def unregister(self, name: str) -> bool:
        """
        Unregister an agent.

        Args:
            name: Name of the agent to unregister

        Returns:
            True if successful, False if agent not found
        """
        if name in self._agents:
            del self._agents[name]
            logger.info(f"Unregistered agent: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[AgentBase]:
        """
        Get an agent by name.

        Args:
            name: Agent name

        Returns:
            Agent instance or None
        """
        return self._agents.get(name)

    def list_agents(self) -> List[dict]:
        """
        List all registered agents with their status.

        Returns:
            List of agent status dictionaries
        """
        return [agent.get_status() for agent in self._agents.values()]

    def list_classes(self) -> List[str]:
        """
        List all registered agent classes.

        Returns:
            List of agent class names
        """
        return list(self._agent_classes.keys())

    async def run_agent(self, name: str, command: str = None) -> dict:
        """
        Run an agent by name.

        Args:
            name: Agent name
            command: Optional command to pass to the agent

        Returns:
            Execution result dictionary
        """
        agent = self.get(name)
        if not agent:
            return {
                "status": "error",
                "error": f"Agent '{name}' not found",
                "timestamp": datetime.now().isoformat()
            }

        return await agent.run(command)

    async def health_check_all(self) -> Dict[str, bool]:
        """
        Run health checks on all agents.

        Returns:
            Dictionary mapping agent names to health status
        """
        results = {}
        for name, agent in self._agents.items():
            try:
                results[name] = await agent.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = False
        return results

    async def start_all(self) -> None:
        """Start all registered agents."""
        for agent in self._agents.values():
            await agent.start()

    async def stop_all(self) -> None:
        """Stop all registered agents."""
        for agent in self._agents.values():
            await agent.stop()


# Global registry instance
agent_registry = AgentRegistry()


def register_agent(name: str = None):
    """
    Decorator to register an agent class.

    Usage:
        @register_agent()
        class MyAgent(AgentBase):
            ...

        @register_agent(name="custom_name")
        class AnotherAgent(AgentBase):
            ...
    """
    def decorator(cls: Type[AgentBase]) -> Type[AgentBase]:
        agent_registry.register_class(cls, name)
        return cls
    return decorator
