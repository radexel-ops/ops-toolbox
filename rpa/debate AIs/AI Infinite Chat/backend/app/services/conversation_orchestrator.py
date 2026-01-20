"""
Conversation Orchestrator
AI간 무제한 대화 관리, 속도 조절, 사용자 개입 처리
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


class ConversationOrchestrator:
    """
    대화 오케스트레이터

    역할:
    - AI간 무제한 대화 실행
    - 턴 관리 및 속도 조절
    - 사용자 개입 처리
    - 실시간 스트리밍 전달
    """

    # 무한루프 방지를 위한 상수
    MIN_TURN_INTERVAL = 2.0  # 최소 턴 간격 (초)
    MAX_ERRORS_BEFORE_STOP = 3  # 연속 에러 시 자동 정지
    RATE_LIMIT_WINDOW = 10.0  # 속도 제한 윈도우 (초)
    MAX_TURNS_PER_WINDOW = 5  # 윈도우 내 최대 턴 수

    def __init__(self, ai_manager: AIManager, settings=None):
        self.ai_manager = ai_manager
        self.master_ai = MasterAI()
        self.config: Optional[ConversationConfig] = None
        self._stop_flag = False
        self._pause_flag = False
        self._turn_count = 0
        self._start_time: float = 0
        self._limit_reached: Optional[str] = None  # 'turns', 'cost', 'time' 또는 None
        self._consecutive_errors = 0  # 연속 에러 카운트
        self._last_turn_time: float = 0  # 마지막 턴 시간
        self._turn_timestamps: List[float] = []  # 최근 턴 타임스탬프 (속도 제한용)
        self._web_search = WebSearchService(settings) if settings else None

    async def start_conversation(
        self,
        config: ConversationConfig,
        on_message: Callable[[Dict[str, Any]], None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        대화 시작 및 무제한 실행
        """
        self.config = config
        self._stop_flag = False
        self._pause_flag = False
        self._turn_count = 0
        self._start_time = time.time()
        self._limit_reached = None

        # 마스터 AI 초기화
        init_result = self.master_ai.initialize_conversation(
            topic=config.topic,
            agent_count=config.agent_count,
            available_models=config.models,
            auto_start=config.auto_start
        )

        # 초기 이미지가 있으면 첫 번째 에이전트에게 전달
        if config.initial_images:
            self.master_ai.state.user_images = config.initial_images
            logger.info(f"[Init] Passing {len(config.initial_images)} initial images to first agent")

        # 초기화 완료 알림
        yield {
            "type": "conversation_started",
            "data": init_result
        }

        # 무제한 대화 루프
        logger.info(f"[Loop] Starting conversation loop, stop_flag: {self._stop_flag}")
        self._consecutive_errors = 0
        self._turn_timestamps = []

        while not self._stop_flag:
            # 일시정지 체크 - 여기서 대기
            if self._pause_flag:
                logger.info(f"[Loop] Entering pause wait, pause_flag: {self._pause_flag}")
            while self._pause_flag and not self._stop_flag:
                await asyncio.sleep(0.1)

            if self._stop_flag:
                logger.info("[Loop] Stop flag detected, breaking")
                break

            # ===== 속도 제한 체크 (무한루프 방지 핵심) =====
            current_time = time.time()

            # 1. 최소 턴 간격 보장
            if self._last_turn_time > 0:
                time_since_last = current_time - self._last_turn_time
                if time_since_last < self.MIN_TURN_INTERVAL:
                    wait_time = self.MIN_TURN_INTERVAL - time_since_last
                    logger.info(f"[RateLimit] Enforcing min interval: waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    current_time = time.time()

            # 2. 슬라이딩 윈도우 속도 제한
            self._turn_timestamps = [t for t in self._turn_timestamps
                                     if current_time - t < self.RATE_LIMIT_WINDOW]
            if len(self._turn_timestamps) >= self.MAX_TURNS_PER_WINDOW:
                oldest = self._turn_timestamps[0]
                wait_time = self.RATE_LIMIT_WINDOW - (current_time - oldest) + 0.5
                if wait_time > 0:
                    logger.warning(f"[RateLimit] Too many turns in window, waiting {wait_time:.1f}s")
                    yield {
                        "type": "rate_limited",
                        "message": f"속도 제한: {wait_time:.0f}초 대기 중...",
                        "wait_seconds": wait_time
                    }
                    await asyncio.sleep(wait_time)

            # 안전 제한 체크
            limit_event = self._check_limits()
            if limit_event:
                yield limit_event
                break

            # 다음 발언자 선택
            agent = self.master_ai.get_next_speaker()
            if not agent:
                logger.error("[Loop] No agent returned, breaking")
                break

            # 턴 시작 시간 기록
            turn_start_time = time.time()
            self._last_turn_time = turn_start_time
            self._turn_timestamps.append(turn_start_time)

            # AI 응답 생성
            response_success = True
            async for event in self._generate_agent_response(agent):
                yield event
                # 에러 이벤트 체크
                if event.get("type") == "error":
                    response_success = False
                # 정지 플래그 체크
                if self._stop_flag:
                    break

            # 에러 카운트 관리
            if response_success:
                self._consecutive_errors = 0
            else:
                self._consecutive_errors += 1
                logger.warning(f"[Loop] Consecutive errors: {self._consecutive_errors}")
                if self._consecutive_errors >= self.MAX_ERRORS_BEFORE_STOP:
                    logger.error(f"[Loop] Too many consecutive errors, stopping")
                    yield {
                        "type": "error",
                        "error": f"연속 {self.MAX_ERRORS_BEFORE_STOP}회 에러 발생으로 대화가 중지되었습니다."
                    }
                    self._stop_flag = True
                    break

            # 턴 카운트 증가
            self._turn_count += 1

            if self._stop_flag:
                break

            # 일시정지 체크 (응답 완료 후)
            if self._pause_flag:
                logger.info(f"[Loop] Paused after turn {self._turn_count}")
                continue  # 루프 처음으로 돌아가서 pause 대기

            # 속도 조절 대기 - 설정된 딜레이 적용 (실시간 속도 변경 반영)
            turn_duration = time.time() - turn_start_time
            elapsed_delay = 0

            while not self._stop_flag and not self._pause_flag:
                # 매 루프마다 현재 속도 설정 다시 읽기 (실시간 반영)
                current_delay = max(self.MIN_TURN_INTERVAL, self.config.speed.delay_seconds)
                remaining_delay = current_delay - turn_duration - elapsed_delay

                if remaining_delay <= 0:
                    break  # 충분히 기다림

                # 짧은 간격으로 sleep (빠른 pause/stop/speed 반응)
                sleep_time = min(0.1, remaining_delay)  # 100ms 단위로 체크
                await asyncio.sleep(sleep_time)
                elapsed_delay += sleep_time

            if elapsed_delay > 0:
                logger.debug(f"[Loop] Waited {elapsed_delay:.1f}s before next turn")

        logger.info(f"[Loop] Conversation ended after {self._turn_count} turns")
        yield {"type": "conversation_ended"}

    async def _perform_web_search_if_needed(self, topic: str, recent_messages: List[Dict]) -> Optional[str]:
        """필요한 경우 웹 검색 수행"""

        # 웹 검색 서비스가 없거나 비활성화된 경우
        if not self._web_search or not self._web_search.is_available():
            return None

        if not self.master_ai.is_web_search_enabled():
            return None

        # 검색 의도 감지
        search_query = None

        # 최근 사용자 메시지에서 검색 의도 확인
        for msg in reversed(recent_messages[-5:]):
            if msg.get('agent_id') == 'user':
                search_query = detect_search_intent(msg.get('content', ''))
                if search_query:
                    break

        # 첫 턴이고 최신 정보가 필요한 주제인 경우 검색
        if not search_query and self._turn_count == 0:
            current_info_keywords = ['최근', '요즘', '현재', '오늘', '지금', '최신', '2024', '2025', '2026']
            if any(kw in topic for kw in current_info_keywords):
                search_query = topic

        if not search_query:
            return None

        try:
            logger.info(f"[WebSearch] Searching for: {search_query}")
            results = await self._web_search.search(search_query, num_results=5)

            if results:
                context = self._web_search.format_results_for_context(results, search_query)
                logger.info(f"[WebSearch] Found {len(results)} results")
                return context
        except Exception as e:
            logger.error(f"[WebSearch] Error: {e}")

        return None

    async def _generate_agent_response(
        self,
        agent: Agent
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """에이전트 응답 생성 (타이핑 효과 포함, 토큰 사용량 추적)"""

        # 웹 검색 수행 (필요한 경우)
        search_context = await self._perform_web_search_if_needed(
            self.config.topic if self.config else "",
            self.master_ai.state.messages[-5:]
        )
        if search_context:
            self.master_ai.set_web_search_context(search_context)

        # 프롬프트 구성
        prompt = self.master_ai.build_prompt_for_agent(agent)

        # 대기 중인 이미지 가져오기
        images = self.master_ai.get_pending_images()

        # 고유 메시지 ID 생성 (프론트엔드 중복 감지용)
        msg_id = f"msg_{uuid.uuid4().hex[:12]}_{int(time.time() * 1000)}"

        # 응답 시작 알림
        yield {
            "type": "agent_start",
            "agent": agent.to_dict(),
            "_msgId": msg_id
        }

        full_response = ""
        typing_delay = self.config.speed.typing_delay
        usage_data = None
        has_error = False
        error_message = ""
        current_msg_id = msg_id  # agent_complete에서 사용

        try:
            if typing_delay > 0:
                # 타이핑 효과 모드: 먼저 전체 응답을 받고, 천천히 표시
                collected_tokens = []
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

                # 에러 발생 시 처리
                if has_error:
                    yield {
                        "type": "error",
                        "agent_id": agent.id,
                        "error": error_message
                    }
                    # 에러 시 일시정지 (무한루프 방지)
                    self._pause_flag = True
                    logger.error(f"[Response] Error occurred, auto-pausing: {error_message}")
                    return

                # 전체 텍스트를 글자 단위로 천천히 전송
                full_text = "".join(collected_tokens)
                for char in full_text:
                    # 정지 플래그 즉시 체크
                    if self._stop_flag:
                        logger.info("[Typing] Stop flag detected, breaking character loop")
                        break

                    # 일시정지 상태면 즉시 대기 (문자 출력 전)
                    while self._pause_flag and not self._stop_flag:
                        await asyncio.sleep(0.1)

                    if self._stop_flag:
                        break

                    yield {
                        "type": "token",
                        "agent_id": agent.id,
                        "content": char
                    }

                    # 현재 속도 설정에 따른 타이핑 딜레이 (실시간 반영)
                    current_typing_delay = self.config.speed.typing_delay if self.config else 0
                    if current_typing_delay > 0 and not self._pause_flag and not self._stop_flag:
                        # 짧은 간격으로 나누어 sleep (빠른 pause/stop 반응)
                        sleep_remaining = current_typing_delay
                        while sleep_remaining > 0 and not self._pause_flag and not self._stop_flag:
                            sleep_chunk = min(0.02, sleep_remaining)  # 20ms 단위로 체크
                            await asyncio.sleep(sleep_chunk)
                            sleep_remaining -= sleep_chunk

            else:
                # 일반 모드: 토큰 즉시 전송 (사용량 추적 포함)
                async for event in self.ai_manager.generate_stream_with_usage(
                    user_message=prompt,
                    model=agent.model,
                    temperature=0.8,
                    max_tokens=2048,
                    images=images
                ):
                    # 정지 플래그 즉시 체크
                    if self._stop_flag:
                        logger.info("[Response] Stop flag detected during streaming")
                        break

                    # 일시정지 상태면 대기 (토큰 출력 전)
                    while self._pause_flag and not self._stop_flag:
                        await asyncio.sleep(0.1)

                    if self._stop_flag:
                        break

                    if event.get("type") == "token":
                        full_response += event["content"]
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

                # 에러 발생 시 처리
                if has_error:
                    yield {
                        "type": "error",
                        "agent_id": agent.id,
                        "error": error_message
                    }
                    # 에러 시 일시정지 (무한루프 방지)
                    self._pause_flag = True
                    logger.error(f"[Response] Error occurred, auto-pausing: {error_message}")
                    return

            # 빈 응답 체크 (무한루프 방지)
            if not full_response.strip():
                logger.warning(f"[Response] Empty response from {agent.model}, auto-pausing")
                yield {
                    "type": "error",
                    "agent_id": agent.id,
                    "error": f"빈 응답이 반환되었습니다. API 키를 확인해주세요."
                }
                self._pause_flag = True
                return

            # 메시지 저장
            self.master_ai.add_message(
                sender=agent.name,
                content=full_response,
                agent_id=agent.id,
                model=agent.model
            )

            # 응답 완료 알림 (사용량 정보 포함)
            complete_event = {
                "type": "agent_complete",
                "agent": agent.to_dict(),
                "content": full_response,
                "_msgId": current_msg_id  # 프론트엔드 중복 감지용
            }
            if usage_data:
                complete_event["usage"] = {
                    "input_tokens": usage_data.get("input_tokens", 0),
                    "output_tokens": usage_data.get("output_tokens", 0),
                    "total_input": usage_data.get("total_input", 0),
                    "total_output": usage_data.get("total_output", 0)
                }
            yield complete_event

        except Exception as e:
            logger.exception(f"[Response] Exception during generation: {e}")
            yield {
                "type": "error",
                "agent_id": agent.id,
                "error": str(e)
            }
            # 예외 발생 시 자동 일시정지 (무한루프 방지)
            self._pause_flag = True
            logger.error(f"[Response] Exception occurred, auto-pausing to prevent infinite loop")

    def user_intervene(self, message: str, images: List[Dict[str, Any]] = None):
        """사용자가 대화에 개입"""
        self.master_ai.user_intervene(message, images=images)

    def pause(self):
        """대화 일시정지"""
        self._pause_flag = True
        self.master_ai.pause()
        logger.info(f"[Orchestrator] Paused - flag: {self._pause_flag}")

    def resume(self):
        """대화 재개"""
        self._pause_flag = False
        self.master_ai.resume()
        logger.info(f"[Orchestrator] Resumed - flag: {self._pause_flag}")

    def stop(self):
        """대화 종료"""
        self._stop_flag = True
        self.master_ai.stop()
        logger.info(f"[Orchestrator] Stopped - flag: {self._stop_flag}")

    def set_speed(self, speed: ConversationSpeed):
        """속도 변경"""
        if self.config:
            self.config.speed = speed
            logger.info(f"[Orchestrator] Speed changed to {speed.value} (typing_delay: {speed.typing_delay}s)")

    def _check_limits(self) -> Optional[Dict[str, Any]]:
        """안전 제한 체크 (백엔드 강제 적용)"""
        if not self.config or not self.config.limits:
            return None

        limits = self.config.limits

        # 턴 제한 체크
        if self._turn_count >= limits.max_turns:
            self._limit_reached = 'turns'
            self._stop_flag = True
            logger.warning(f"[Limits] Max turns reached: {self._turn_count}/{limits.max_turns}")
            return {
                "type": "limit_reached",
                "limit_type": "turns",
                "message": f"최대 턴 수({limits.max_turns}회)에 도달하여 대화가 자동 종료되었습니다.",
                "value": self._turn_count,
                "max_value": limits.max_turns
            }

        # 시간 제한 체크
        elapsed_minutes = (time.time() - self._start_time) / 60
        if elapsed_minutes >= limits.max_minutes:
            self._limit_reached = 'time'
            self._stop_flag = True
            logger.warning(f"[Limits] Max time reached: {elapsed_minutes:.1f}/{limits.max_minutes} minutes")
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
        return {
            "master_ai": self.master_ai.get_state(),
            "config": {
                "topic": self.config.topic if self.config else "",
                "agent_count": self.config.agent_count if self.config else 0,
                "speed": self.config.speed.value if self.config else "normal"
            },
            "is_paused": self._pause_flag,
            "is_stopped": self._stop_flag
        }
