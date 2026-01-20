"""Pydantic schemas for API models"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """Chat message"""
    id: Optional[str] = None
    role: MessageRole
    content: str
    timestamp: Optional[datetime] = None
    model: Optional[str] = None


class Conversation(BaseModel):
    """Conversation containing multiple messages"""
    id: str
    messages: List[Message] = []
    created_at: datetime
    updated_at: Optional[datetime] = None


class Agent(BaseModel):
    """AI Agent configuration"""
    id: str
    name: str
    model: str
    provider: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7


class ChatSettings(BaseModel):
    """Chat session settings"""
    agents: List[Agent] = []
    speed: str = "normal"  # "very_fast", "fast", "normal", "slow", "very_slow"
    master_ai_enabled: bool = True


class ConversationSpeedEnum(str, Enum):
    """Valid conversation speeds"""
    VERY_FAST = "very_fast"
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"
    VERY_SLOW = "very_slow"


class StartConversationRequest(BaseModel):
    """대화 시작 요청 검증"""
    type: str = "start_conversation"
    session_id: str = Field(..., min_length=10, max_length=100)
    topic: str = Field(..., min_length=1, max_length=500)
    agent_count: int = Field(default=2, ge=2, le=5)
    speed: ConversationSpeedEnum = ConversationSpeedEnum.NORMAL
    auto_start: bool = True
    models: Optional[List[Dict[str, str]]] = None

    @field_validator('topic')
    @classmethod
    def sanitize_topic(cls, v: str) -> str:
        # 기본 XSS 방지
        return v.strip()[:500]


class UserInterveneRequest(BaseModel):
    """사용자 개입 요청 검증"""
    type: str = "user_intervene"
    session_id: str = Field(..., min_length=10, max_length=100)
    content: str = Field(default="", max_length=10000)
    file_ids: List[str] = Field(default_factory=list)

    @field_validator('content')
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        return v.strip()[:10000]


class SetSpeedRequest(BaseModel):
    """속도 변경 요청 검증"""
    type: str = "set_speed"
    session_id: str = Field(..., min_length=10, max_length=100)
    speed: ConversationSpeedEnum


class SessionControlRequest(BaseModel):
    """세션 제어 요청 (pause, resume, stop)"""
    type: str
    session_id: str = Field(..., min_length=10, max_length=100)
