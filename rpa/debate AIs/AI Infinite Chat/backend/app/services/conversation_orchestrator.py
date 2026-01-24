"""
Conversation Orchestrator
AI간 무제한 대화 관리, 속도 조절, 사용자 개입 처리

리팩토링 완료:
- 상태 플래그 관리 강화 (Lock 기반 동시성 제어)
- 상세 로깅 추가
- asyncio.sleep 중 상태 변경 즉시 반응
- 에러 발생 시 자동 복구 로직
- Race Condition 방지
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator, Callable
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from app.services.master_ai import MasterAI, Agent
from app.services.ai_manager import AIManager
from app.services.web_search import WebSearchService, detect_search_intent
from app.services.event_log import ConversationEventLog, EventType, event_log_manager
# 디버그 로거 (서비스 안정화 후 삭제 예정)
from app.utils.debug_logger import (
    log_action as debug_action,
    log_ws_send as debug_ws_send,
    log_state_change as debug_state,
    log_agent as debug_agent,
    log_error as debug_error,
    log_system as debug_system
)


class ConversationSpeed(str, Enum):
    """대화 속도"""
    VERY_FAST = "very_fast"    # 즉시 표시, 0.5초 대기
    FAST = "fast"              # 즉시 표시, 1초 대기
    NORMAL = "normal"          # 즉시 표시, 2초 대기
    SLOW = "slow"              # 타이핑 효과 (0.03초/글자)
    VERY_SLOW = "very_slow"    # 타이핑 효과 (0.06초/글자)

    @property
    def delay_seconds(self) -> float:
        """턴 사이 대기 시간"""
        delays = {
            "very_fast": 0.3,   # 즉시 다음 턴
            "fast": 0.8,        # 빠른 전환
            "normal": 1.5,      # 적당한 대기
            "slow": 2.0,        # 여유있는 대기
            "very_slow": 3.0    # 충분한 생각 시간
        }
        return delays.get(self.value, 1.5)

    @property
    def typing_delay(self) -> float:
        """글자당 타이핑 딜레이 (0이면 즉시 표시)"""
        delays = {
            "very_fast": 0,
            "fast": 0,
            "normal": 0,
            "slow": 0.03,       # 글자당 0.03초 (약 33글자/초)
            "very_slow": 0.08   # 글자당 0.08초 (약 12글자/초, 사람 타이핑 속도)
        }
        return delays.get(self.value, 0)


@dataclass
class ConversationLimits:
    """대화 안전 제한"""
    max_turns: int = 100        # 최대 턴 수
    max_cost: float = 1.0       # 최대 비용 (USD)
    max_minutes: int = 30       # 최대 시간 (분)
    pause_on_inactive: bool = True  # 비활성 시 자동 일시정지


@dataclass
class ConversationConfig:
    """대화 설정"""
    topic: str
    agent_count: int = 2
    speed: ConversationSpeed = ConversationSpeed.NORMAL
    auto_start: bool = True  # True: 즉시 시작, False: 마스터AI 제안 후 승인
    models: List[Dict[str, str]] = None  # 사용할 모델들
    limits: ConversationLimits = None  # 안전 제한
    initial_images: List[Dict[str, Any]] = None  # 초기 첨부 이미지
    existing_agents: List[Dict[str, Any]] = None  # 대화 재개 시 기존 에이전트

    def __post_init__(self):
        if self.models is None:
            self.models = [
                {"id": "gpt-5-mini", "provider": "openai"},
                {"id": "gemini-3-flash-preview", "provider": "google"}
            ]
        if self.limits is None:
            self.limits = ConversationLimits()
        if self.initial_images is None:
            self.initial_images = []
        if self.existing_agents is None:
            self.existing_agents = []


class StateManager:
    """
    상태 플래그 관리자

    Lock 기반으로 동시성 제어하여 Race Condition 방지
    상태 변경 시 상세 로깅 수행
    """

    def __init__(self, orchestrator_id: str):
        self._id = orchestrator_id
        self._stop_flag = False
        self._pause_flag = False
        self._lock = asyncio.Lock()
        self._state_change_event = asyncio.Event()

    async def set_stop(self, value: bool, reason: str = ""):
        """정지 플래그 설정"""
        async with self._lock:
            old_value = self._stop_flag
            self._stop_flag = value
            if old_value != value:
                logger.info(f"[State:{self._id}] STOP: {old_value} -> {value} (reason: {reason})")
                self._state_change_event.set()

    async def set_pause(self, value: bool, reason: str = ""):
        """일시정지 플래그 설정"""
        async with self._lock:
            old_value = self._pause_flag
            self._pause_flag = value
            if old_value != value:
                logger.info(f"[State:{self._id}] PAUSE: {old_value} -> {value} (reason: {reason})")
                self._state_change_event.set()

    @property
    def is_stopped(self) -> bool:
        return self._stop_flag

    @property
    def is_paused(self) -> bool:
        return self._pause_flag

    def clear_event(self):
        """상태 변경 이벤트 초기화"""
        self._state_change_event.clear()

    async def wait_for_state_change(self, timeout: float = 0.1) -> bool:
        """상태 변경 대기 (timeout 내에 변경되면 True 반환)"""
        try:
            await asyncio.wait_for(self._state_change_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False


class ConversationOrchestrator:
    """
    대화 오케스트레이터

    역할:
    - AI간 무제한 대화 실행
    - 턴 관리 및 속도 조절
    - 사용자 개입 처리
    - 실시간 스트리밍 전달

    개선 사항:
    - StateManager를 통한 안전한 상태 관리
    - 상세 로깅
    - 에러 발생 시 자동 복구
    """

    # 무한루프 방지를 위한 상수
    MIN_TURN_INTERVAL = 2.0  # 최소 턴 간격 (초)
    MAX_ERRORS_BEFORE_STOP = 3  # 연속 에러 시 자동 정지
    RATE_LIMIT_WINDOW = 10.0  # 속도 제한 윈도우 (초)
    MAX_TURNS_PER_WINDOW = 5  # 윈도우 내 최대 턴 수
    MAX_RETRY_ATTEMPTS = 2  # 에러 발생 시 최대 재시도 횟수
    RETRY_DELAY = 1.0  # 재시도 대기 시간 (초)

    def __init__(self, ai_manager: AIManager, settings=None, session_id: str = None):
        self._id = uuid.uuid4().hex[:8]  # 고유 ID (로깅용)
        self.ai_manager = ai_manager
        self.master_ai = MasterAI()
        self.config: Optional[ConversationConfig] = None

        # 세션 ID 및 이벤트 로그
        self._session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        self._event_log: Optional[ConversationEventLog] = None

        # 상태 관리자
        self._state = StateManager(self._id)

        # 레거시 플래그 (하위 호환성)
        self._stop_flag = False
        self._pause_flag = False

        self._turn_count = 0
        self._start_time: float = 0
        self._limit_reached: Optional[str] = None
        self._consecutive_errors = 0
        self._last_turn_time: float = 0
        self._turn_timestamps: List[float] = []
        self._web_search = WebSearchService(settings) if settings else None

        logger.info(f"[Orchestrator:{self._id}] Created (session: {self._session_id[:8]})")

    def _emit_event(self, event_type: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        이벤트 발생 - 로그에 기록하고 WebSocket 전송용 딕셔너리 반환

        모든 이벤트는 이 메서드를 통해 발생하여 일관된 시퀀스 관리 보장
        """
        if self._event_log is None:
            # 이벤트 로그가 없으면 레거시 방식으로 반환
            return {"type": event_type, **(data or {})}

        # 이벤트 로그에 기록
        event = self._event_log.append(event_type, data or {})

        # WebSocket 전송용 딕셔너리 반환 (seq 포함)
        return event.to_dict()

    def get_event_log(self) -> Optional[ConversationEventLog]:
        """현재 세션의 이벤트 로그 반환"""
        return self._event_log

    def get_events_since(self, since_seq: int = 0) -> List[Dict[str, Any]]:
        """특정 시퀀스 이후의 이벤트 반환 (재동기화용)"""
        if self._event_log is None:
            return []
        events = self._event_log.get_events_since(since_seq)
        return [e.to_dict() for e in events]

    async def start_conversation(
        self,
        config: ConversationConfig,
        on_message: Callable[[Dict[str, Any]], None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        대화 시작 및 무제한 실행
        """
        self.config = config
        self._turn_count = 0
        self._start_time = time.time()
        self._limit_reached = None
        self._consecutive_errors = 0
        self._turn_timestamps = []

        # 이벤트 로그 초기화 (Event Sourcing)
        self._event_log = event_log_manager.get_or_create(self._session_id)

        # 상태 초기화
        await self._state.set_stop(False, "conversation_start")
        await self._state.set_pause(False, "conversation_start")
        self._stop_flag = False
        self._pause_flag = False

        debug_system(self._id, "CONVERSATION_STARTING", {
            "topic_preview": config.topic[:100],
            "agent_count": config.agent_count,
            "existing_agents_count": len(config.existing_agents) if config.existing_agents else 0,
            "has_initial_images": len(config.initial_images) > 0 if config.initial_images else False
        })
        logger.info(f"[Orchestrator:{self._id}] Starting conversation - topic: {config.topic[:50]}...")

        # 마스터 AI 초기화 (기존 에이전트가 있으면 재사용)
        init_result = self.master_ai.initialize_conversation(
            topic=config.topic,
            agent_count=config.agent_count,
            available_models=config.models,
            auto_start=config.auto_start,
            existing_agents=config.existing_agents
        )

        debug_agent(self._id, "AGENTS_INITIALIZED", {
            "agents": [{"name": a.get("name"), "model": a.get("model")} for a in init_result.get("agents", [])]
        })

        # 초기 이미지가 있으면 첫 번째 에이전트에게 전달
        if config.initial_images:
            self.master_ai.state.user_images = config.initial_images
            logger.info(f"[Orchestrator:{self._id}] Passing {len(config.initial_images)} initial images")

        # 초기화 완료 알림 (이벤트 로그에 기록)
        debug_ws_send(self._id, "conversation_started", {"agent_count": len(init_result.get("agents", []))})
        yield self._emit_event(EventType.CONVERSATION_STARTED.value, {"data": init_result})

        # 무제한 대화 루프
        logger.info(f"[Orchestrator:{self._id}] Entering main loop")

        while not self._state.is_stopped and not self._stop_flag:
            # 일시정지 처리 - 이벤트 기반 대기
            await self._handle_pause_state()

            if self._state.is_stopped or self._stop_flag:
                debug_system(self._id, "STOP_DETECTED_AFTER_PAUSE", {"turn_count": self._turn_count})
                logger.info(f"[Orchestrator:{self._id}] Stop detected after pause check")
                break

            # 속도 제한 체크
            rate_limit_event = await self._apply_rate_limiting()
            if rate_limit_event:
                debug_system(self._id, "RATE_LIMITED", {"event": rate_limit_event})
                yield self._emit_event(EventType.RATE_LIMITED.value, rate_limit_event)

            # 안전 제한 체크
            limit_event = self._check_limits()
            if limit_event:
                debug_system(self._id, "LIMIT_REACHED", {"limit_type": limit_event.get("limit_type")})
                yield self._emit_event(EventType.LIMIT_REACHED.value, limit_event)
                break

            # 다음 발언자 선택
            agent = self.master_ai.get_next_speaker()
            if not agent:
                debug_error(self._id, "NO_AGENT", "No agent returned from master_ai")
                logger.error(f"[Orchestrator:{self._id}] No agent returned")
                break

            debug_agent(self._id, "TURN_START", {
                "turn": self._turn_count + 1,
                "agent_name": agent.name,
                "agent_model": agent.model
            })

            # 턴 시작
            turn_start_time = time.time()
            self._last_turn_time = turn_start_time
            self._turn_timestamps.append(turn_start_time)

            logger.info(f"[Orchestrator:{self._id}] Turn {self._turn_count + 1}: {agent.name} ({agent.model})")

            # AI 응답 생성 (재시도 로직 포함)
            response_success = False
            for attempt in range(self.MAX_RETRY_ATTEMPTS + 1):
                if self._state.is_stopped or self._stop_flag:
                    break

                async for event in self._generate_agent_response_with_recovery(agent, attempt):
                    yield event
                    if event.get("type") == "agent_complete":
                        response_success = True
                    elif event.get("type") == "error" and attempt < self.MAX_RETRY_ATTEMPTS:
                        logger.warning(f"[Orchestrator:{self._id}] Error on attempt {attempt + 1}, will retry")
                    if self._state.is_stopped or self._stop_flag:
                        break

                if response_success or self._state.is_stopped or self._stop_flag:
                    break

                if attempt < self.MAX_RETRY_ATTEMPTS:
                    logger.info(f"[Orchestrator:{self._id}] Waiting {self.RETRY_DELAY}s before retry")
                    await self._interruptible_sleep(self.RETRY_DELAY)

            # 에러 카운트 관리
            if response_success:
                self._consecutive_errors = 0
                debug_agent(self._id, "TURN_COMPLETE", {"turn": self._turn_count + 1, "success": True})
            else:
                self._consecutive_errors += 1
                debug_error(self._id, "TURN_ERROR", f"Consecutive errors: {self._consecutive_errors}", {
                    "turn": self._turn_count + 1,
                    "consecutive_errors": self._consecutive_errors
                })
                logger.warning(f"[Orchestrator:{self._id}] Consecutive errors: {self._consecutive_errors}")
                if self._consecutive_errors >= self.MAX_ERRORS_BEFORE_STOP:
                    debug_system(self._id, "MAX_ERRORS_STOPPING", {
                        "consecutive_errors": self._consecutive_errors,
                        "turn_count": self._turn_count
                    })
                    logger.error(f"[Orchestrator:{self._id}] Too many errors, stopping")
                    yield self._emit_event(EventType.ERROR.value, {
                        "error": f"연속 {self.MAX_ERRORS_BEFORE_STOP}회 에러 발생으로 대화가 중지되었습니다."
                    })
                    await self._state.set_stop(True, "max_errors_reached")
                    self._stop_flag = True
                    break

            self._turn_count += 1

            if self._state.is_stopped or self._stop_flag:
                debug_system(self._id, "STOP_DETECTED_END_OF_TURN", {"turn_count": self._turn_count})
                break

            # 턴 간 대기 (인터럽트 가능)
            await self._wait_between_turns(turn_start_time)

        debug_system(self._id, "CONVERSATION_ENDED", {
            "total_turns": self._turn_count,
            "stop_flag": self._stop_flag,
            "state_is_stopped": self._state.is_stopped,
            "consecutive_errors": self._consecutive_errors
        })
        logger.info(f"[Orchestrator:{self._id}] Conversation ended after {self._turn_count} turns")
        debug_ws_send(self._id, "conversation_ended", {"turns": self._turn_count})
        yield self._emit_event(EventType.CONVERSATION_ENDED.value, {"turns": self._turn_count})

    async def _handle_pause_state(self):
        """일시정지 상태 처리 - 이벤트 기반 대기"""
        if self._state.is_paused or self._pause_flag:
            logger.info(f"[Orchestrator:{self._id}] Entering pause state")

        pause_start = time.time()
        while (self._state.is_paused or self._pause_flag) and not self._state.is_stopped and not self._stop_flag:
            # 100ms 간격으로 상태 체크 (빠른 반응)
            self._state.clear_event()
            await self._state.wait_for_state_change(timeout=0.1)

            # 긴 일시정지 시 로그
            pause_duration = time.time() - pause_start
            if pause_duration > 0 and int(pause_duration) % 30 == 0 and int(pause_duration) > 0:
                logger.debug(f"[Orchestrator:{self._id}] Still paused for {pause_duration:.0f}s")

        if pause_start and (time.time() - pause_start) > 0.5:
            logger.info(f"[Orchestrator:{self._id}] Exiting pause state (duration: {time.time() - pause_start:.1f}s)")

    async def _apply_rate_limiting(self) -> Optional[Dict[str, Any]]:
        """속도 제한 적용"""
        current_time = time.time()

        # 1. 최소 턴 간격 보장
        if self._last_turn_time > 0:
            time_since_last = current_time - self._last_turn_time
            if time_since_last < self.MIN_TURN_INTERVAL:
                wait_time = self.MIN_TURN_INTERVAL - time_since_last
                logger.debug(f"[Orchestrator:{self._id}] Min interval wait: {wait_time:.1f}s")
                await self._interruptible_sleep(wait_time)
                current_time = time.time()

        # 2. 슬라이딩 윈도우 속도 제한
        self._turn_timestamps = [
            t for t in self._turn_timestamps
            if current_time - t < self.RATE_LIMIT_WINDOW
        ]

        if len(self._turn_timestamps) >= self.MAX_TURNS_PER_WINDOW:
            oldest = self._turn_timestamps[0]
            wait_time = self.RATE_LIMIT_WINDOW - (current_time - oldest) + 0.5
            if wait_time > 0:
                logger.warning(f"[Orchestrator:{self._id}] Rate limit hit, waiting {wait_time:.1f}s")
                await self._interruptible_sleep(wait_time)
                return {
                    "type": "rate_limited",
                    "message": f"속도 제한: {wait_time:.0f}초 대기 중...",
                    "wait_seconds": wait_time
                }

        return None

    async def _interruptible_sleep(self, duration: float):
        """인터럽트 가능한 sleep - 상태 변경 시 즉시 반환"""
        elapsed = 0
        interval = 0.05  # 50ms 간격으로 체크

        while elapsed < duration:
            if self._state.is_stopped or self._stop_flag:
                logger.debug(f"[Orchestrator:{self._id}] Sleep interrupted by stop")
                return
            if self._state.is_paused or self._pause_flag:
                logger.debug(f"[Orchestrator:{self._id}] Sleep interrupted by pause")
                return

            sleep_time = min(interval, duration - elapsed)
            await asyncio.sleep(sleep_time)
            elapsed += sleep_time

    async def _wait_between_turns(self, turn_start_time: float):
        """턴 간 대기 - 실시간 속도 설정 반영"""
        turn_duration = time.time() - turn_start_time
        elapsed_delay = 0

        while not self._state.is_stopped and not self._stop_flag:
            if self._state.is_paused or self._pause_flag:
                return  # 일시정지 시 즉시 반환, 루프 처음에서 대기

            # 현재 속도 설정 확인 (실시간 반영)
            current_delay = max(self.MIN_TURN_INTERVAL, self.config.speed.delay_seconds) if self.config else self.MIN_TURN_INTERVAL
            remaining = current_delay - turn_duration - elapsed_delay

            if remaining <= 0:
                break

            sleep_time = min(0.1, remaining)
            await asyncio.sleep(sleep_time)
            elapsed_delay += sleep_time

    async def _generate_agent_response_with_recovery(
        self,
        agent: Agent,
        attempt: int = 0
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """에이전트 응답 생성 (복구 로직 포함)"""
        async for event in self._generate_agent_response(agent, is_retry=(attempt > 0)):
            yield event

    async def _perform_web_search_if_needed(self, topic: str, recent_messages: List[Dict]) -> Optional[str]:
        """필요한 경우 웹 검색 수행"""
        if not self._web_search or not self._web_search.is_available():
            return None

        if not self.master_ai.is_web_search_enabled():
            return None

        search_query = None

        for msg in reversed(recent_messages[-5:]):
            if msg.get('agent_id') == 'user':
                search_query = detect_search_intent(msg.get('content', ''))
                if search_query:
                    break

        if not search_query and self._turn_count == 0:
            current_info_keywords = ['최근', '요즘', '현재', '오늘', '지금', '최신', '2024', '2025', '2026']
            if any(kw in topic for kw in current_info_keywords):
                search_query = topic

        if not search_query:
            return None

        try:
            logger.info(f"[Orchestrator:{self._id}] Web search: {search_query}")
            results = await self._web_search.search(search_query, num_results=5)
            if results:
                context = self._web_search.format_results_for_context(results, search_query)
                logger.info(f"[Orchestrator:{self._id}] Found {len(results)} search results")
                return context
        except Exception as e:
            logger.error(f"[Orchestrator:{self._id}] Web search error: {e}")

        return None

    async def _generate_agent_response(
        self,
        agent: Agent,
        is_retry: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """에이전트 응답 생성"""

        # 웹 검색 수행 (필요한 경우)
        if not is_retry:
            search_context = await self._perform_web_search_if_needed(
                self.config.topic if self.config else "",
                self.master_ai.state.messages[-5:]
            )
            if search_context:
                self.master_ai.set_web_search_context(search_context)

        # 프롬프트 구성
        prompt = self.master_ai.build_prompt_for_agent(agent)
        images = self.master_ai.get_pending_images()
        msg_id = f"msg_{uuid.uuid4().hex[:12]}_{int(time.time() * 1000)}"

        # 응답 시작 알림 (agent_start는 로그에 기록하지만 토큰은 너무 많아서 제외)
        yield self._emit_event(EventType.AGENT_START.value, {
            "agent": agent.to_dict(),
            "_msgId": msg_id,
            "_retry": is_retry
        })

        full_response = ""
        typing_delay = self.config.speed.typing_delay if self.config else 0
        usage_data = None
        has_error = False
        error_message = ""

        was_interrupted = False  # 스트리밍 중단 여부 추적

        try:
            if typing_delay > 0:
                # 타이핑 효과 모드
                async for event in self._generate_with_typing_effect(agent, prompt, images, typing_delay):
                    if event.get("_internal_response"):
                        full_response = event["_internal_response"]
                    elif event.get("_internal_usage"):
                        usage_data = event["_internal_usage"]
                    elif event.get("_internal_error"):
                        has_error = True
                        error_message = event["_internal_error"]
                    else:
                        yield event

                    if self._state.is_stopped or self._stop_flag:
                        was_interrupted = True
                        logger.info(f"[Orchestrator:{self._id}] Stop detected during typing effect")
                        break
            else:
                # 일반 모드
                async for event in self.ai_manager.generate_stream_with_usage(
                    user_message=prompt,
                    model=agent.model,
                    temperature=0.8,
                    max_tokens=2048,
                    images=images
                ):
                    if self._state.is_stopped or self._stop_flag:
                        was_interrupted = True
                        logger.info(f"[Orchestrator:{self._id}] Stop detected during streaming")
                        break

                    # 일시정지 처리
                    while (self._state.is_paused or self._pause_flag) and not self._state.is_stopped and not self._stop_flag:
                        await asyncio.sleep(0.1)

                    if self._state.is_stopped or self._stop_flag:
                        was_interrupted = True
                        break

                    if event.get("type") == "token":
                        full_response += event["content"]
                        # 토큰은 이벤트 로그에 기록하지 않음 (너무 많음)
                        # seq 없이 전송하여 프론트엔드에서 특별 처리
                        yield {
                            "type": "token",
                            "agent_id": agent.id,
                            "content": event["content"]
                        }
                    elif event.get("type") == "usage":
                        usage_data = event
                    elif event.get("type") == "error":
                        has_error = True
                        error_message = event.get("content", "Unknown error")

            # 에러 처리
            if has_error:
                logger.error(f"[Orchestrator:{self._id}] Response error: {error_message}")
                yield self._emit_event(EventType.ERROR.value, {
                    "agent_id": agent.id,
                    "error": error_message,
                    "recoverable": True
                })
                return

            # 스트리밍 중단 시에도 부분 응답이 있으면 저장 및 전송
            if was_interrupted:
                logger.info(f"[Orchestrator:{self._id}] Streaming interrupted, partial response length: {len(full_response)}")
                if full_response.strip():
                    # 부분 응답이라도 저장
                    self.master_ai.add_message(
                        sender=agent.name,
                        content=full_response,
                        agent_id=agent.id,
                        model=agent.model
                    )
                    # 중단된 응답 완료 알림 (interrupted 플래그 포함)
                    yield self._emit_event(EventType.AGENT_COMPLETE.value, {
                        "agent": agent.to_dict(),
                        "content": full_response,
                        "_msgId": msg_id,
                        "interrupted": True  # 중단됨 표시
                    })
                else:
                    # 빈 응답이면 agent_complete를 빈 내용으로 전송 (프론트엔드에서 빈 카드 방지)
                    yield self._emit_event(EventType.AGENT_COMPLETE.value, {
                        "agent": agent.to_dict(),
                        "content": "[응답 생성 중 중단됨]",
                        "_msgId": msg_id,
                        "interrupted": True
                    })
                return

            # 빈 응답 체크
            if not full_response.strip():
                logger.warning(f"[Orchestrator:{self._id}] Empty response from {agent.model}")
                yield self._emit_event(EventType.ERROR.value, {
                    "agent_id": agent.id,
                    "error": "빈 응답이 반환되었습니다. API 키를 확인해주세요.",
                    "recoverable": True
                })
                return

            # 메시지 저장
            self.master_ai.add_message(
                sender=agent.name,
                content=full_response,
                agent_id=agent.id,
                model=agent.model
            )

            # 응답 완료 알림
            complete_data = {
                "agent": agent.to_dict(),
                "content": full_response,
                "_msgId": msg_id
            }
            if usage_data:
                complete_data["usage"] = {
                    "input_tokens": usage_data.get("input_tokens", 0),
                    "output_tokens": usage_data.get("output_tokens", 0),
                    "total_input": usage_data.get("total_input", 0),
                    "total_output": usage_data.get("total_output", 0)
                }
            yield self._emit_event(EventType.AGENT_COMPLETE.value, complete_data)

        except Exception as e:
            logger.exception(f"[Orchestrator:{self._id}] Exception during generation: {e}")
            yield self._emit_event(EventType.ERROR.value, {
                "agent_id": agent.id,
                "error": str(e),
                "recoverable": True
            })

    async def _generate_with_typing_effect(
        self,
        agent: Agent,
        prompt: str,
        images: List[Dict[str, Any]],
        typing_delay: float
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """타이핑 효과 모드 생성"""
        collected_tokens = []
        full_response = ""
        usage_data = None
        has_error = False
        error_message = ""

        async for event in self.ai_manager.generate_stream_with_usage(
            user_message=prompt,
            model=agent.model,
            temperature=0.8,
            max_tokens=2048,
            images=images
        ):
            if event.get("type") == "token":
                collected_tokens.append(event["content"])
                full_response += event["content"]
            elif event.get("type") == "usage":
                usage_data = event
            elif event.get("type") == "error":
                has_error = True
                error_message = event.get("content", "Unknown error")

        if has_error:
            yield {"_internal_error": error_message}
            return

        # 전체 텍스트를 글자 단위로 전송
        for char in full_response:
            if self._state.is_stopped or self._stop_flag:
                break

            while (self._state.is_paused or self._pause_flag) and not self._state.is_stopped and not self._stop_flag:
                await asyncio.sleep(0.1)

            if self._state.is_stopped or self._stop_flag:
                break

            # 토큰은 이벤트 로그에 기록하지 않음 (너무 많음)
            # seq 없이 전송하여 프론트엔드에서 특별 처리
            yield {
                "type": "token",
                "agent_id": agent.id,
                "content": char
            }

            # 타이핑 딜레이 (인터럽트 가능)
            current_typing_delay = self.config.speed.typing_delay if self.config else 0
            if current_typing_delay > 0:
                await self._interruptible_sleep(current_typing_delay)

        yield {"_internal_response": full_response}
        if usage_data:
            yield {"_internal_usage": usage_data}

    def user_intervene(self, message: str, images: List[Dict[str, Any]] = None):
        """사용자가 대화에 개입"""
        logger.info(f"[Orchestrator:{self._id}] User intervention: {message[:50]}...")
        self.master_ai.user_intervene(message, images=images)
        # 이벤트 로그에 사용자 메시지 기록
        if self._event_log:
            self._event_log.append(EventType.USER_MESSAGE.value, {
                "content": message,
                "hasFiles": bool(images)
            })

    def pause(self):
        """대화 일시정지"""
        self._pause_flag = True
        asyncio.create_task(self._state.set_pause(True, "user_request"))
        self.master_ai.pause()
        # 이벤트 로그에 기록
        if self._event_log:
            self._event_log.append(EventType.CONVERSATION_PAUSED.value, {})
        logger.info(f"[Orchestrator:{self._id}] Paused")

    def resume(self):
        """대화 재개"""
        self._pause_flag = False
        asyncio.create_task(self._state.set_pause(False, "user_request"))
        self.master_ai.resume()
        # 이벤트 로그에 기록
        if self._event_log:
            self._event_log.append(EventType.CONVERSATION_RESUMED.value, {})
        logger.info(f"[Orchestrator:{self._id}] Resumed")

    def stop(self):
        """대화 종료"""
        self._stop_flag = True
        asyncio.create_task(self._state.set_stop(True, "user_request"))
        self.master_ai.stop()
        # 이벤트 로그에 기록
        if self._event_log:
            self._event_log.append(EventType.CONVERSATION_STOPPED.value, {})
        logger.info(f"[Orchestrator:{self._id}] Stopped")

    def set_speed(self, speed: ConversationSpeed):
        """속도 변경"""
        if self.config:
            old_speed = self.config.speed
            self.config.speed = speed
            logger.info(f"[Orchestrator:{self._id}] Speed: {old_speed.value} -> {speed.value}")

    def _check_limits(self) -> Optional[Dict[str, Any]]:
        """안전 제한 체크"""
        if not self.config or not self.config.limits:
            return None

        limits = self.config.limits

        # 턴 제한
        if self._turn_count >= limits.max_turns:
            self._limit_reached = 'turns'
            self._stop_flag = True
            asyncio.create_task(self._state.set_stop(True, "max_turns"))
            logger.warning(f"[Orchestrator:{self._id}] Limit: turns ({self._turn_count}/{limits.max_turns})")
            return {
                "type": "limit_reached",
                "limit_type": "turns",
                "message": f"최대 턴 수({limits.max_turns}회)에 도달하여 대화가 자동 종료되었습니다.",
                "value": self._turn_count,
                "max_value": limits.max_turns
            }

        # 시간 제한
        elapsed_minutes = (time.time() - self._start_time) / 60
        if elapsed_minutes >= limits.max_minutes:
            self._limit_reached = 'time'
            self._stop_flag = True
            asyncio.create_task(self._state.set_stop(True, "max_time"))
            logger.warning(f"[Orchestrator:{self._id}] Limit: time ({elapsed_minutes:.1f}/{limits.max_minutes}min)")
            return {
                "type": "limit_reached",
                "limit_type": "time",
                "message": f"최대 시간({limits.max_minutes}분)에 도달하여 대화가 자동 종료되었습니다.",
                "value": round(elapsed_minutes, 1),
                "max_value": limits.max_minutes
            }

        return None

    def get_state(self) -> Dict[str, Any]:
        """현재 상태"""
        state = {
            "id": self._id,
            "session_id": self._session_id,
            "master_ai": self.master_ai.get_state(),
            "config": {
                "topic": self.config.topic if self.config else "",
                "agent_count": self.config.agent_count if self.config else 0,
                "speed": self.config.speed.value if self.config else "normal"
            },
            "is_paused": self._pause_flag or self._state.is_paused,
            "is_stopped": self._stop_flag or self._state.is_stopped,
            "turn_count": self._turn_count,
            "consecutive_errors": self._consecutive_errors
        }
        # 이벤트 로그 정보 추가
        if self._event_log:
            state["event_log"] = {
                "current_seq": self._event_log.current_seq,
                "event_count": self._event_log.event_count
            }
        return state
