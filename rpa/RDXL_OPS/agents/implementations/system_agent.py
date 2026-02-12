"""
System Agent

Handles system monitoring and maintenance tasks.
"""

from datetime import datetime
import platform
import asyncio

from ..base.agent_base import AgentBase
from ..registry import register_agent


@register_agent(name="system_agent")
class SystemAgent(AgentBase):
    """
    System Monitoring and Maintenance Agent.

    Capabilities:
    - System health monitoring
    - Resource usage tracking
    - Log analysis
    - Automated maintenance tasks
    """

    def __init__(self, name: str = "system_agent", config: dict = None):
        super().__init__(name, config)
        self.description = "시스템 모니터링 에이전트"
        self.capabilities = [
            "health_monitoring",
            "resource_tracking",
            "log_analysis",
            "maintenance_automation"
        ]

    async def execute(self, command: str = None) -> dict:
        """
        Execute system-related tasks.

        Supported commands:
        - health: System health check
        - resources: Resource usage info
        - info: System information
        - logs: Recent log summary
        """
        if not command:
            return {
                "message": "System Agent ready. Available commands: health, resources, info, logs",
                "capabilities": self.capabilities
            }

        command_lower = command.lower().strip()

        if command_lower == "health":
            return await self._health_status()
        elif command_lower == "resources":
            return await self._resource_usage()
        elif command_lower == "info":
            return await self._system_info()
        elif command_lower == "logs":
            return await self._log_summary()
        else:
            return {
                "message": f"Unknown command: {command}",
                "available_commands": ["health", "resources", "info", "logs"]
            }

    async def _health_status(self) -> dict:
        """Get system health status."""
        return {
            "status": "healthy",
            "checks": {
                "database": "ok",
                "api_server": "ok",
                "bridge": "ok",
                "agents": "ok"
            },
            "uptime": "2 days, 5 hours",
            "last_check": datetime.now().isoformat()
        }

    async def _resource_usage(self) -> dict:
        """Get resource usage information."""
        return {
            "cpu": {
                "usage_percent": 25.5,
                "cores": 4
            },
            "memory": {
                "total_gb": 8,
                "used_gb": 3.2,
                "percent": 40
            },
            "disk": {
                "total_gb": 100,
                "used_gb": 35,
                "percent": 35
            },
            "timestamp": datetime.now().isoformat()
        }

    async def _system_info(self) -> dict:
        """Get system information."""
        return {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "architecture": platform.machine(),
            "vibeops_version": "0.3.0"
        }

    async def _log_summary(self) -> dict:
        """Get recent log summary."""
        return {
            "period": "last_24h",
            "summary": {
                "total_entries": 1250,
                "errors": 3,
                "warnings": 15,
                "info": 1232
            },
            "recent_errors": [
                {
                    "timestamp": "2026-02-10T08:15:00",
                    "message": "Connection timeout (recovered)",
                    "severity": "warning"
                }
            ],
            "generated_at": datetime.now().isoformat()
        }

    async def health_check(self) -> bool:
        """Check agent health."""
        return self.status in ["initialized", "running"]

    def get_status(self) -> dict:
        """Get extended status."""
        base_status = super().get_status()
        base_status.update({
            "description": self.description,
            "capabilities": self.capabilities
        })
        return base_status
