"""
VibeOps Bridge System

Real-time connection between web dashboard and server terminal.
Handles team context propagation for multi-tenant AI interactions.
"""

import sys

from .team_context import TeamContext, SessionState, SessionManager, session_manager
from .message_types import (
    MessageType,
    BridgeMessage,
    CommandPayload,
    StreamPayload,
    ResponsePayload
)

__all__ = [
    # Context
    "TeamContext",
    "SessionState",
    "SessionManager",
    "session_manager",
    # Messages
    "MessageType",
    "BridgeMessage",
    "CommandPayload",
    "StreamPayload",
    "ResponsePayload",
]

# PTY-based bridge server (Linux only)
if sys.platform != "win32":
    try:
        from .bridge_server import BridgeServer, bridge_server, run_claude_simple, stream_claude_simple
        __all__.extend([
            "BridgeServer",
            "bridge_server",
            "run_claude_simple",
            "stream_claude_simple",
        ])
    except ImportError:
        pass  # PTY not available
