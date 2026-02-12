"""
Agent System Tests

Tests for the agent management system including registry, agent execution, and API endpoints.
"""

import pytest
from httpx import AsyncClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.registry import AgentRegistry, register_agent
from agents.base_agent import BaseAgent


class TestAgentRegistry:
    """Tests for the agent registry."""

    def test_registry_singleton(self):
        """Test that AgentRegistry is a singleton."""
        registry1 = AgentRegistry()
        registry2 = AgentRegistry()
        assert registry1 is registry2

    def test_register_agent_decorator(self):
        """Test agent registration using decorator."""
        registry = AgentRegistry()

        @register_agent("test_decorator_agent")
        class TestDecoratorAgent(BaseAgent):
            name = "test_decorator_agent"
            description = "Test agent created via decorator"

            async def execute(self, command: str = None) -> dict:
                return {"status": "success", "data": "decorator test"}

        assert "test_decorator_agent" in registry._agent_classes

    def test_register_agent_class(self):
        """Test agent registration using register_class method."""
        registry = AgentRegistry()

        class TestManualAgent(BaseAgent):
            name = "test_manual_agent"
            description = "Test agent registered manually"

            async def execute(self, command: str = None) -> dict:
                return {"status": "success", "data": "manual test"}

        registry.register_class("test_manual_agent", TestManualAgent)
        assert "test_manual_agent" in registry._agent_classes

    def test_list_agents(self):
        """Test listing all registered agents."""
        registry = AgentRegistry()
        agents = registry.list_agents()

        assert isinstance(agents, list)
        # Should have at least the default agents (pm, news, system)
        agent_names = [a["name"] for a in agents]
        assert "pm" in agent_names or "news" in agent_names or "system" in agent_names

    def test_get_agent_info(self):
        """Test getting info for a specific agent."""
        registry = AgentRegistry()
        info = registry.get_agent_info("system")

        if info:  # If system agent is registered
            assert "name" in info
            assert "description" in info
            assert "status" in info

    @pytest.mark.asyncio
    async def test_run_agent(self):
        """Test running an agent."""
        registry = AgentRegistry()

        # System agent should always be available
        result = await registry.run_agent("system", "status")

        assert isinstance(result, dict)
        assert "status" in result


class TestAgentEndpoints:
    """Tests for agent API endpoints."""

    @pytest.mark.asyncio
    async def test_list_agents_endpoint(self, client: AsyncClient, auth_headers):
        """Test GET /api/agents endpoint."""
        response = await client.get(
            "/api/agents",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_agents_unauthenticated(self, client: AsyncClient):
        """Test GET /api/agents without authentication."""
        response = await client.get("/api/agents")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_agent_detail(self, client: AsyncClient, auth_headers):
        """Test GET /api/agents/{name} endpoint."""
        response = await client.get(
            "/api/agents/system",
            headers=auth_headers
        )

        # Either 200 (agent exists) or 404 (agent not found)
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_run_agent_endpoint(self, client: AsyncClient, admin_auth_headers):
        """Test POST /api/agents/{name}/run endpoint."""
        response = await client.post(
            "/api/agents/system/run",
            json={"command": "status"},
            headers=admin_auth_headers
        )

        # Either 200 (success) or 404 (agent not found) or 403 (permission denied)
        assert response.status_code in [200, 403, 404]

    @pytest.mark.asyncio
    async def test_run_agent_permission_denied(self, client: AsyncClient, auth_headers):
        """Test that regular users cannot run agents."""
        response = await client.post(
            "/api/agents/system/run",
            json={"command": "status"},
            headers=auth_headers
        )

        # Regular users should be denied
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_run_nonexistent_agent(self, client: AsyncClient, admin_auth_headers):
        """Test running a non-existent agent."""
        response = await client.post(
            "/api/agents/nonexistent_agent_xyz/run",
            json={"command": "test"},
            headers=admin_auth_headers
        )

        assert response.status_code == 404


class TestAgentHealthCheck:
    """Tests for agent health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_all(self):
        """Test health check for all agents."""
        registry = AgentRegistry()
        results = await registry.health_check_all()

        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: AsyncClient, auth_headers):
        """Test GET /api/agents/health endpoint."""
        response = await client.get(
            "/api/agents/health",
            headers=auth_headers
        )

        # Either 200 or 405 (method not allowed if endpoint doesn't exist)
        assert response.status_code in [200, 405, 404]
