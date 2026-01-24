"""
Conversation Event Log - Event Sourcing Architecture
대화의 모든 이벤트를 시퀀스 번호와 함께 불변(append-only)으로 기록

핵심 원칙:
- Single Source of Truth: 백엔드가 유일한 진실의 원천
- Append-Only: 이벤트는 삭제/수정하지 않고 추가만 함
- Sequence-Based: 모든 이벤트에 고유 시퀀스 번호 부여
- Recoverable: 누락된 이벤트 재요청 가능
"""

import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
from threading import Lock

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """대화 이벤트 타입"""
    # Conversation Lifecycle
    CONVERSATION_STARTED = "conversation_started"
    CONVERSATION_ENDED = "conversation_ended"
    CONVERSATION_PAUSED = "paused"
    CONVERSATION_RESUMED = "resumed"
    CONVERSATION_STOPPED = "stopped"

    # Agent Events
    AGENT_START = "agent_start"
    AGENT_TOKEN = "token"
    AGENT_COMPLETE = "agent_complete"

    # User Events
    USER_MESSAGE = "user_message"
    USER_INTERVENE = "user_intervention_ack"

    # System Events
    ERROR = "error"
    LIMIT_REACHED = "limit_reached"
    SPEED_CHANGED = "speed_changed"
    RATE_LIMITED = "rate_limited"


@dataclass
class ConversationEvent:
    """대화 이벤트 - 불변 데이터"""
    seq: int                      # 시퀀스 번호 (1부터 시작, 단조 증가)
    type: str                     # 이벤트 타입
    data: Dict[str, Any]          # 이벤트 데이터
    timestamp: float              # Unix timestamp
    event_id: str = ""            # 고유 이벤트 ID

    def __post_init__(self):
        if not self.event_id:
            self.event_id = f"evt_{uuid.uuid4().hex[:12]}_{int(self.timestamp * 1000)}"

    def to_dict(self) -> Dict[str, Any]:
        """WebSocket 전송용 딕셔너리"""
        return {
            "seq": self.seq,
            "type": self.type,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            **self.data  # 이벤트 데이터를 최상위 레벨로 펼침
        }


class ConversationEventLog:
    """
    대화 이벤트 로그

    모든 이벤트를 시퀀스 번호와 함께 불변(append-only)으로 기록
    - Thread-safe: Lock 기반 동시성 제어
    - 누락된 이벤트 재요청 지원
    - 메시지 파생 뷰 제공
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._events: List[ConversationEvent] = []
        self._current_seq = 0
        self._lock = Lock()
        self._created_at = time.time()

        logger.info(f"[EventLog:{session_id[:8]}] Created")

    def append(self, event_type: str, data: Dict[str, Any] = None) -> ConversationEvent:
        """
        이벤트 추가 (Thread-safe)

        Returns:
            생성된 ConversationEvent
        """
        with self._lock:
            self._current_seq += 1
            event = ConversationEvent(
                seq=self._current_seq,
                type=event_type,
                data=data or {},
                timestamp=time.time()
            )
            self._events.append(event)

            logger.debug(f"[EventLog:{self.session_id[:8]}] Event #{event.seq}: {event_type}")
            return event

    def get_events_since(self, since_seq: int = 0) -> List[ConversationEvent]:
        """
        특정 시퀀스 이후의 모든 이벤트 반환

        Args:
            since_seq: 이 시퀀스 이후의 이벤트만 반환 (0이면 전체)

        Returns:
            이벤트 리스트
        """
        with self._lock:
            if since_seq == 0:
                return list(self._events)
            return [e for e in self._events if e.seq > since_seq]

    def get_event(self, seq: int) -> Optional[ConversationEvent]:
        """특정 시퀀스의 이벤트 반환"""
        with self._lock:
            if 1 <= seq <= len(self._events):
                return self._events[seq - 1]  # seq는 1부터 시작
            return None

    @property
    def current_seq(self) -> int:
        """현재 시퀀스 번호"""
        with self._lock:
            return self._current_seq

    @property
    def event_count(self) -> int:
        """총 이벤트 수"""
        with self._lock:
            return len(self._events)

    def get_messages(self) -> List[Dict[str, Any]]:
        """
        이벤트 로그에서 메시지 목록 파생

        agent_complete와 user_message 이벤트만 추출하여 메시지 형태로 반환
        """
        messages = []

        with self._lock:
            for event in self._events:
                if event.type == EventType.AGENT_COMPLETE.value:
                    messages.append({
                        "id": event.event_id,
                        "seq": event.seq,
                        "agent": event.data.get("agent"),
                        "content": event.data.get("content", ""),
                        "timestamp": event.timestamp,
                        "usage": event.data.get("usage"),
                        "interrupted": event.data.get("interrupted", False)
                    })
                elif event.type == EventType.USER_MESSAGE.value:
                    messages.append({
                        "id": event.event_id,
                        "seq": event.seq,
                        "isUser": True,
                        "content": event.data.get("content", ""),
                        "timestamp": event.timestamp,
                        "isInitialTopic": event.data.get("isInitialTopic", False),
                        "hasFiles": event.data.get("hasFiles", False)
                    })

        return messages

    def get_agents(self) -> List[Dict[str, Any]]:
        """이벤트 로그에서 에이전트 목록 파생"""
        with self._lock:
            for event in self._events:
                if event.type == EventType.CONVERSATION_STARTED.value:
                    return event.data.get("data", {}).get("agents", [])
        return []

    def get_token_usage(self) -> Dict[str, Any]:
        """이벤트 로그에서 토큰 사용량 파생"""
        total_input = 0
        total_output = 0
        history = []

        with self._lock:
            for event in self._events:
                if event.type == EventType.AGENT_COMPLETE.value:
                    usage = event.data.get("usage")
                    if usage:
                        total_input += usage.get("input_tokens", 0)
                        total_output += usage.get("output_tokens", 0)
                        history.append({
                            "model": event.data.get("agent", {}).get("model"),
                            "inputTokens": usage.get("input_tokens", 0),
                            "outputTokens": usage.get("output_tokens", 0)
                        })

        return {
            "totalInput": total_input,
            "totalOutput": total_output,
            "history": history
        }

    def get_state_snapshot(self) -> Dict[str, Any]:
        """
        현재 상태 스냅샷 반환

        프론트엔드 초기화 또는 재연결 시 사용
        """
        return {
            "session_id": self.session_id,
            "current_seq": self.current_seq,
            "event_count": self.event_count,
            "messages": self.get_messages(),
            "agents": self.get_agents(),
            "tokenUsage": self.get_token_usage(),
            "created_at": self._created_at
        }

    def to_dict(self) -> Dict[str, Any]:
        """전체 이벤트 로그를 딕셔너리로"""
        with self._lock:
            return {
                "session_id": self.session_id,
                "events": [e.to_dict() for e in self._events],
                "current_seq": self._current_seq
            }


class EventLogManager:
    """
    세션별 이벤트 로그 관리자

    여러 대화 세션의 이벤트 로그를 관리
    """

    def __init__(self):
        self._logs: Dict[str, ConversationEventLog] = {}
        self._lock = Lock()

    def get_or_create(self, session_id: str) -> ConversationEventLog:
        """세션의 이벤트 로그 반환 (없으면 생성)"""
        with self._lock:
            if session_id not in self._logs:
                self._logs[session_id] = ConversationEventLog(session_id)
                logger.info(f"[EventLogManager] Created log for session: {session_id[:8]}")
            return self._logs[session_id]

    def get(self, session_id: str) -> Optional[ConversationEventLog]:
        """세션의 이벤트 로그 반환 (없으면 None)"""
        with self._lock:
            return self._logs.get(session_id)

    def remove(self, session_id: str):
        """세션 로그 제거 (메모리 정리)"""
        with self._lock:
            if session_id in self._logs:
                del self._logs[session_id]
                logger.info(f"[EventLogManager] Removed log for session: {session_id[:8]}")

    def cleanup_old_sessions(self, max_age_seconds: float = 3600):
        """오래된 세션 정리"""
        current_time = time.time()
        to_remove = []

        with self._lock:
            for session_id, log in self._logs.items():
                if current_time - log._created_at > max_age_seconds:
                    to_remove.append(session_id)

            for session_id in to_remove:
                del self._logs[session_id]

        if to_remove:
            logger.info(f"[EventLogManager] Cleaned up {len(to_remove)} old sessions")


# 전역 이벤트 로그 매니저
event_log_manager = EventLogManager()
