"""
Team Context for Bridge System

Manages team-specific context for AI interactions.
Each session carries team context including merged guidelines.
"""

from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass, field


class TeamContext(BaseModel):
    """
    Team context carried through AI sessions.

    Contains:
    - Team identification
    - User information
    - Merged guidelines for AI prompts
    - Available knowledge paths
    """

    # Team info
    team_id: int
    team_slug: str
    team_name: str

    # User info
    user_id: int
    user_email: str
    user_role: str

    # Session info
    session_id: str
    created_at: datetime = None

    # Guidelines (pre-merged for efficiency)
    merged_guidelines: str = ""

    # Available paths for AI reference
    paths: Dict[str, str] = {}

    # Available knowledge files
    master_knowledge_files: List[str] = []
    team_knowledge_files: List[str] = []

    def __init__(self, **data):
        if data.get("created_at") is None:
            data["created_at"] = datetime.utcnow()
        super().__init__(**data)

    def to_system_prompt(self) -> str:
        """
        Generate system prompt prefix with team context.

        This is prepended to user messages to give AI
        full context about who it's working with.
        """
        return f"""# Session Context

You are working with:
- Team: {self.team_name} ({self.team_slug})
- User: {self.user_email} ({self.user_role})
- Session: {self.session_id}

## Team Working Directory
- Team Data: {self.paths.get('team_data', 'N/A')}
- Team Agents: {self.paths.get('team_agents', 'N/A')}
- Team Knowledge: {self.paths.get('team_knowledge', 'N/A')}

---

{self.merged_guidelines}
"""


@dataclass
class SessionState:
    """
    State for an active bridge session.

    Tracks:
    - Team context
    - Conversation history
    - Current operation status
    """

    session_id: str
    team_context: TeamContext
    conversation_history: List[Dict] = field(default_factory=list)
    current_operation: Optional[str] = None
    operation_progress: int = 0
    last_activity: datetime = field(default_factory=datetime.utcnow)

    def add_message(self, role: str, content: str):
        """Add message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.last_activity = datetime.utcnow()

    def get_conversation_for_ai(self, max_messages: int = 20) -> List[Dict]:
        """
        Get recent conversation history formatted for AI.

        Returns list of {"role": "user/assistant", "content": "..."}
        """
        recent = self.conversation_history[-max_messages:]
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in recent
        ]

    def set_operation(self, operation: str):
        """Set current operation (for progress tracking)"""
        self.current_operation = operation
        self.operation_progress = 0

    def update_progress(self, progress: int):
        """Update operation progress (0-100)"""
        self.operation_progress = min(100, max(0, progress))

    def complete_operation(self):
        """Mark operation as complete"""
        self.current_operation = None
        self.operation_progress = 100


class SessionManager:
    """
    Manages active bridge sessions.

    Each session is isolated by team and user.
    """

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}

    def create_session(
        self,
        session_id: str,
        team_context: TeamContext
    ) -> SessionState:
        """Create new session with team context"""
        state = SessionState(
            session_id=session_id,
            team_context=team_context
        )
        self._sessions[session_id] = state
        return state

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get session by ID"""
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> bool:
        """Remove session"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def get_user_sessions(self, user_id: int) -> List[SessionState]:
        """Get all sessions for a user"""
        return [
            s for s in self._sessions.values()
            if s.team_context.user_id == user_id
        ]

    def get_team_sessions(self, team_slug: str) -> List[SessionState]:
        """Get all sessions for a team"""
        return [
            s for s in self._sessions.values()
            if s.team_context.team_slug == team_slug
        ]

    def cleanup_stale_sessions(self, max_age_hours: int = 24) -> int:
        """Remove sessions older than max_age_hours"""
        now = datetime.utcnow()
        stale = []

        for session_id, state in self._sessions.items():
            age = (now - state.last_activity).total_seconds() / 3600
            if age > max_age_hours:
                stale.append(session_id)

        for session_id in stale:
            del self._sessions[session_id]

        return len(stale)

    @property
    def active_count(self) -> int:
        """Number of active sessions"""
        return len(self._sessions)


# Global session manager instance
session_manager = SessionManager()
