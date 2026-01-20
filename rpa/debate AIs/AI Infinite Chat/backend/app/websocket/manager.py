"""WebSocket Connection Manager"""

import asyncio
import logging
from typing import List, Dict, Any, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections with thread safety.
    Uses asyncio.Lock for concurrent access protection.
    """

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept and store a new WebSocket connection"""
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.debug(f"[WS Manager] Connection added. Total: {len(self._connections)}")

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        async with self._lock:
            self._connections.discard(websocket)
        logger.debug(f"[WS Manager] Connection removed. Total: {len(self._connections)}")

    async def send_text(self, websocket: WebSocket, message: str):
        """Send text message to a specific client"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.warning(f"[WS Manager] Failed to send text: {e}")
            await self.disconnect(websocket)
            raise

    async def send_json(self, websocket: WebSocket, data: Dict[str, Any]):
        """Send JSON message to a specific client"""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.warning(f"[WS Manager] Failed to send JSON: {e}")
            await self.disconnect(websocket)
            raise

    async def broadcast_text(self, message: str):
        """Broadcast text message to all connected clients"""
        # Create a snapshot of connections to avoid modification during iteration
        async with self._lock:
            connections = list(self._connections)

        dead_connections = []
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"[WS Manager] Broadcast failed for a connection: {e}")
                dead_connections.append(connection)

        # Remove dead connections
        if dead_connections:
            async with self._lock:
                for conn in dead_connections:
                    self._connections.discard(conn)

    async def broadcast_json(self, data: Dict[str, Any]):
        """Broadcast JSON message to all connected clients"""
        # Create a snapshot of connections to avoid modification during iteration
        async with self._lock:
            connections = list(self._connections)

        dead_connections = []
        for connection in connections:
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.warning(f"[WS Manager] Broadcast JSON failed for a connection: {e}")
                dead_connections.append(connection)

        # Remove dead connections
        if dead_connections:
            async with self._lock:
                for conn in dead_connections:
                    self._connections.discard(conn)

    @property
    def connection_count(self) -> int:
        """Return number of active connections"""
        return len(self._connections)

    @property
    def active_connections(self) -> List[WebSocket]:
        """Return list of active connections (for backward compatibility)"""
        return list(self._connections)
