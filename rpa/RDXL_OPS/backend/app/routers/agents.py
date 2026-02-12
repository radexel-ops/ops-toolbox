"""
Agents Router

API endpoints for managing and executing agents.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
import sys
import os

# Add project root to path for agent imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from agents.registry import agent_registry
from agents.implementations import PMAgent, NewsAgent, SystemAgent

from ..dependencies import get_current_user
from ..models import User

router = APIRouter()


# Pydantic models for request/response
class AgentRunRequest(BaseModel):
    command: Optional[str] = None


class AgentResponse(BaseModel):
    name: str
    status: str
    version: Optional[str] = "1.0.0"
    description: Optional[str] = None
    capabilities: Optional[List[str]] = None
    last_run: Optional[str] = None


class AgentRunResponse(BaseModel):
    agent: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
    duration: Optional[str] = None
    timestamp: str


# Initialize default agents on module load
def _init_default_agents():
    """Initialize default agents if not already registered."""
    try:
        if not agent_registry.get("pm_agent"):
            agent_registry.create_agent("PMAgent", "pm_agent")
        if not agent_registry.get("news_agent"):
            agent_registry.create_agent("NewsAgent", "news_agent")
        if not agent_registry.get("system_agent"):
            agent_registry.create_agent("SystemAgent", "system_agent")
    except Exception as e:
        print(f"Warning: Could not initialize default agents: {e}")


_init_default_agents()


@router.get("/agents", response_model=List[AgentResponse])
async def list_agents(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of all registered agents.

    Returns agent status and capabilities.
    """
    agents = agent_registry.list_agents()
    return [
        AgentResponse(
            name=a.get("name"),
            status=a.get("status"),
            version=a.get("version", "1.0.0"),
            description=a.get("description"),
            capabilities=a.get("capabilities"),
            last_run=a.get("last_run")
        )
        for a in agents
    ]


@router.get("/agents/classes")
async def list_agent_classes(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of available agent classes.

    These can be instantiated to create new agent instances.
    """
    return {
        "classes": agent_registry.list_classes(),
        "count": len(agent_registry.list_classes())
    }


@router.get("/agents/{agent_name}", response_model=AgentResponse)
async def get_agent(
    agent_name: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get details of a specific agent.
    """
    agent = agent_registry.get(agent_name)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_name}' not found"
        )

    status_info = agent.get_status()
    return AgentResponse(
        name=status_info.get("name"),
        status=status_info.get("status"),
        version=status_info.get("version", "1.0.0"),
        description=status_info.get("description"),
        capabilities=status_info.get("capabilities"),
        last_run=status_info.get("last_run")
    )


@router.post("/agents/{agent_name}/run", response_model=AgentRunResponse)
async def run_agent(
    agent_name: str,
    request: AgentRunRequest = AgentRunRequest(),
    current_user: User = Depends(get_current_user)
):
    """
    Execute an agent with an optional command.

    Different agents support different commands.
    Call without command to see available options.
    """
    agent = agent_registry.get(agent_name)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_name}' not found"
        )

    result = await agent_registry.run_agent(agent_name, request.command)

    return AgentRunResponse(
        agent=agent_name,
        status=result.get("status"),
        result=result.get("result"),
        error=result.get("error"),
        duration=result.get("duration"),
        timestamp=result.get("timestamp")
    )


@router.post("/agents/{agent_name}/start")
async def start_agent(
    agent_name: str,
    current_user: User = Depends(get_current_user)
):
    """
    Start an agent.

    Only team_admin and super_admin can start agents.
    """
    if current_user.role.value not in ["super_admin", "team_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can start agents"
        )

    agent = agent_registry.get(agent_name)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_name}' not found"
        )

    await agent.start()
    return {"success": True, "message": f"Agent '{agent_name}' started"}


@router.post("/agents/{agent_name}/stop")
async def stop_agent(
    agent_name: str,
    current_user: User = Depends(get_current_user)
):
    """
    Stop an agent.

    Only team_admin and super_admin can stop agents.
    """
    if current_user.role.value not in ["super_admin", "team_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can stop agents"
        )

    agent = agent_registry.get(agent_name)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_name}' not found"
        )

    await agent.stop()
    return {"success": True, "message": f"Agent '{agent_name}' stopped"}


@router.get("/agents/health/all")
async def health_check_all_agents(
    current_user: User = Depends(get_current_user)
):
    """
    Run health checks on all agents.
    """
    results = await agent_registry.health_check_all()
    all_healthy = all(results.values())

    return {
        "overall_status": "healthy" if all_healthy else "degraded",
        "agents": results
    }
