"""
Bridge Router

WebSocket-based real-time communication for AI interactions.
Integrates team context with each session.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import json
import uuid
from datetime import datetime

from ..database import get_db, async_session
from ..models import User, Team
from ..services.auth_service import auth_service
from ..services.knowledge_service import knowledge_service
from ..services.claude_service import claude_service
from ..dependencies import get_current_user
import logging

logger = logging.getLogger(__name__)

# Import bridge components
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from bridge.team_context import TeamContext, SessionState, session_manager
from bridge.message_types import MessageType, BridgeMessage, CommandPayload, StreamPayload, ResponsePayload

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept and store connection"""
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        """Remove connection"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_message(self, session_id: str, message: BridgeMessage):
        """Send message to specific session"""
        websocket = self.active_connections.get(session_id)
        if websocket:
            await websocket.send_json(message.model_dump(mode="json"))

    async def broadcast_to_team(self, team_slug: str, message: BridgeMessage):
        """Broadcast message to all sessions of a team"""
        for state in session_manager.get_team_sessions(team_slug):
            await self.send_message(state.session_id, message)


# Global connection manager
manager = ConnectionManager()


async def authenticate_websocket(token: str) -> Optional[tuple[User, Team]]:
    """
    Authenticate WebSocket connection using JWT token.

    Returns (user, team) tuple or None if invalid.
    """
    payload = auth_service.decode_token(token)
    if not payload:
        return None

    async with async_session() as db:
        user_id = int(payload.get("sub"))
        user = await auth_service.get_user_by_id(db, user_id)

        if not user or not user.is_active:
            return None

        team = None
        if user.team_id:
            result = await db.execute(
                select(Team).where(Team.id == user.team_id)
            )
            team = result.scalar_one_or_none()

        return user, team


async def create_team_context(user: User, team: Optional[Team]) -> TeamContext:
    """Create team context for session"""
    team_slug = team.slug if team else "default"
    team_name = team.name if team else "Default"
    team_id = team.id if team else 0

    # Get merged guidelines
    context_data = knowledge_service.get_team_context(team_slug)

    return TeamContext(
        team_id=team_id,
        team_slug=team_slug,
        team_name=team_name,
        user_id=user.id,
        user_email=user.email,
        user_role=user.role.value,
        session_id=str(uuid.uuid4()),
        merged_guidelines=context_data["guidelines"],
        paths=context_data["paths"],
        master_knowledge_files=context_data["master_knowledge_files"],
        team_knowledge_files=context_data["team_knowledge_files"]
    )


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    WebSocket endpoint for AI interactions.

    Flow:
    1. Authenticate via token query param
    2. Create team context
    3. Handle messages with context
    """
    # Authenticate
    auth_result = await authenticate_websocket(token)
    if not auth_result:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    user, team = auth_result

    # Create team context
    team_context = await create_team_context(user, team)
    session_state = session_manager.create_session(
        team_context.session_id,
        team_context
    )

    # Connect
    await manager.connect(websocket, team_context.session_id)

    # Send welcome message
    welcome = BridgeMessage(
        type=MessageType.STATUS,
        payload={
            "status": "connected",
            "session_id": team_context.session_id,
            "team": team_context.team_name,
            "user": user.email
        },
        session_id=team_context.session_id
    )
    await manager.send_message(team_context.session_id, welcome)

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()

            # Parse message type
            msg_type = data.get("type", "command")

            if msg_type == "ping":
                # Respond to ping
                pong = BridgeMessage(
                    type=MessageType.PONG,
                    payload={"timestamp": datetime.now().isoformat()},
                    session_id=team_context.session_id
                )
                await manager.send_message(team_context.session_id, pong)

            elif msg_type == "command":
                # Process user command
                payload = data.get("payload", {})
                user_text = payload.get("text", "")
                use_streaming = payload.get("streaming", True)

                if not user_text:
                    continue

                # Add to conversation history
                session_state.add_message("user", user_text)

                # Set processing status
                session_state.set_operation("processing")
                processing = BridgeMessage(
                    type=MessageType.STREAM,
                    payload=StreamPayload(
                        status="processing",
                        message="Processing your request...",
                        progress=10
                    ).model_dump(),
                    session_id=team_context.session_id
                )
                await manager.send_message(team_context.session_id, processing)

                # Working directory for this team
                working_dir = f"/home/vibeops/vibeops/teams/{team_context.team_slug}"

                try:
                    if use_streaming and claude_service.is_available:
                        # Streaming mode - send chunks as they arrive
                        response_chunks = []

                        async def send_chunk(chunk: str):
                            response_chunks.append(chunk)
                            stream_msg = BridgeMessage(
                                type=MessageType.STREAM,
                                payload=StreamPayload(
                                    status="streaming",
                                    message=chunk,
                                    progress=50
                                ).model_dump(),
                                session_id=team_context.session_id
                            )
                            await manager.send_message(team_context.session_id, stream_msg)

                        async for chunk in claude_service.stream_query(
                            prompt=user_text,
                            team_context=team_context.merged_guidelines,
                            working_dir=working_dir,
                            chunk_callback=send_chunk
                        ):
                            pass  # Chunks are sent via callback

                        response_text = "".join(response_chunks)

                    elif claude_service.is_available:
                        # Non-streaming mode
                        response_text = await claude_service.query(
                            prompt=user_text,
                            team_context=team_context.merged_guidelines,
                            working_dir=working_dir
                        )
                    else:
                        # Fallback message if Claude Code is not available
                        response_text = await claude_service.query(
                            prompt=user_text,
                            team_context=team_context.merged_guidelines,
                            working_dir=working_dir
                        )

                except Exception as e:
                    logger.error(f"Claude Code query failed: {e}")
                    response_text = f"""[Error processing request]

{str(e)}

Please try again or contact administrator.
"""

                # Add AI response to history
                session_state.add_message("assistant", response_text)
                session_state.complete_operation()

                # Send final response
                response = BridgeMessage(
                    type=MessageType.RESPONSE,
                    payload=ResponsePayload(
                        status="completed",
                        result=response_text
                    ).model_dump(),
                    session_id=team_context.session_id
                )
                await manager.send_message(team_context.session_id, response)

    except WebSocketDisconnect:
        # Clean up on disconnect
        manager.disconnect(team_context.session_id)
        session_manager.remove_session(team_context.session_id)


@router.get("/sessions")
async def list_active_sessions(
    current_user: User = Depends(get_current_user)
):
    """List active sessions (admin only sees all, others see own)"""
    if current_user.is_super_admin:
        sessions = [
            {
                "session_id": s.session_id,
                "team": s.team_context.team_name,
                "user": s.team_context.user_email,
                "last_activity": s.last_activity.isoformat()
            }
            for s in session_manager._sessions.values()
        ]
    else:
        sessions = [
            {
                "session_id": s.session_id,
                "team": s.team_context.team_name,
                "last_activity": s.last_activity.isoformat()
            }
            for s in session_manager.get_user_sessions(current_user.id)
        ]

    return {
        "count": len(sessions),
        "sessions": sessions
    }


@router.get("/context")
async def get_current_context(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get team context for current user (preview without WebSocket)"""
    team = None
    if current_user.team_id:
        result = await db.execute(
            select(Team).where(Team.id == current_user.team_id)
        )
        team = result.scalar_one_or_none()

    team_context = await create_team_context(current_user, team)

    return {
        "team_id": team_context.team_id,
        "team_slug": team_context.team_slug,
        "team_name": team_context.team_name,
        "user_email": team_context.user_email,
        "user_role": team_context.user_role,
        "paths": team_context.paths,
        "guidelines_preview": team_context.merged_guidelines[:500] + "..." if len(team_context.merged_guidelines) > 500 else team_context.merged_guidelines
    }
