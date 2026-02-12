"""
Bridge Message Types

Defines message protocol for web-terminal communication.
"""

from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any


class MessageType(str, Enum):
    """WebSocket message types"""

    # Client → Server
    COMMAND = "command"           # User command
    PING = "ping"                 # Connection check

    # Server → Client
    RESPONSE = "response"         # Command response
    STREAM = "stream"             # Streaming data
    STATUS = "status"             # Status update
    ERROR = "error"               # Error message
    PONG = "pong"                 # Ping response


class BridgeMessage(BaseModel):
    """Standard bridge message format"""

    type: MessageType
    payload: Any
    timestamp: datetime = None
    session_id: Optional[str] = None

    def __init__(self, **data):
        if data.get("timestamp") is None:
            data["timestamp"] = datetime.now()
        super().__init__(**data)


class CommandPayload(BaseModel):
    """Payload for command messages"""

    text: str
    target_agent: str = "pm"


class StreamPayload(BaseModel):
    """Payload for stream messages"""

    status: str  # "processing", "completed", "error"
    message: str
    progress: Optional[int] = None  # 0-100


class ResponsePayload(BaseModel):
    """Payload for response messages"""

    status: str  # "completed", "error"
    result: Any
