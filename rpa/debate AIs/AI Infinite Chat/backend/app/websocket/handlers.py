"""
WebSocket Message Handlers
main.py에서 분리된 WebSocket 메시지 처리 로직
유지보수성 향상 및 코드 충돌 방지를 위해 핸들러별로 분리
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable, Awaitable, List
from fastapi import WebSocket

from app.services.conversation_orchestrator import (
    ConversationOrchestrator,
    ConversationConfig,
    ConversationSpeed,
    ConversationLimits
)
from app.services.ai_manager import AIManager
from app.websocket.manager import ConnectionManager
# 디버그 로거 (서비스 안정화 후 삭제 예정)
from app.utils.debug_logger import (
    log_action as debug_action,
    log_ws_recv as debug_ws_recv,
    log_ws_send as debug_ws_send,
    log_state_change as debug_state,
    log_agent as debug_agent,
    log_error as debug_error,
    log_system as debug_system
)

logger = logging.getLogger(__name__)


class WebSocketMessageHandler:
    """
    WebSocket 메시지 핸들러

    각 메시지 타입별로 핸들러 메서드를 분리하여 유지보수성 향상
    Merge Conflict 방지를 위해 핸들러 로직을 별도 클래스로 분리
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        ai_manager: AIManager,
        settings,
        active_conversations: Dict[str, ConversationOrchestrator],
        session_metadata: Dict[str, Dict[str, Any]],
        session_lock: asyncio.Lock
    ):
        self.connection_manager = connection_manager
        self.ai_manager = ai_manager
        self.settings = settings
        self.active_conversations = active_conversations
        self.session_metadata = session_metadata
        self.session_lock = session_lock

        # 핸들러 매핑 (메시지 타입 -> 핸들러 메서드)
        self._handlers: Dict[str, Callable] = {
            "start_conversation": self._handle_start_conversation,
            "user_intervene": self._handle_user_intervene,
            "pause": self._handle_pause,
            "resume": self._handle_resume,
            "stop": self._handle_stop,
            "set_speed": self._handle_set_speed,
            "resume_conversation": self._handle_resume_conversation,
            "get_state": self._handle_get_state,
            "ping": self._handle_ping,
            "message": self._handle_legacy_message,
            "sync_events": self._handle_sync_events,
        }

    async def handle_message(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
        run_conversation_callback: Callable
    ) -> Optional[str]:
        """
        메시지 라우팅 및 처리

        Args:
            websocket: WebSocket 연결
            data: 수신한 메시지 데이터
            run_conversation_callback: 대화 실행 콜백 함수

        Returns:
            session_id (새 세션 시작 시) 또는 None
        """
        message_type = data.get("type", "")
        session_id = data.get("session_id")

        # 디버그 로그: WebSocket 메시지 수신
        debug_ws_recv(session_id or "new", message_type, data)

        # 세션 ID로 orchestrator 조회
        orchestrator = self.active_conversations.get(session_id) if session_id else None
        logger.info(f"[Handler] Received: {message_type}, session_id: {session_id}, orchestrator exists: {orchestrator is not None}")

        # 세션 활동 시간 업데이트
        if session_id and session_id in self.session_metadata:
            self.session_metadata[session_id]['last_activity'] = time.time()

        # 핸들러 조회 및 실행
        handler = self._handlers.get(message_type)
        if handler:
            return await handler(
                websocket=websocket,
                data=data,
                session_id=session_id,
                orchestrator=orchestrator,
                run_conversation_callback=run_conversation_callback
            )
        else:
            logger.warning(f"[Handler] Unknown message type: {message_type}")
            return None

    async def _handle_start_conversation(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
        session_id: str,
        orchestrator: Optional[ConversationOrchestrator],
        run_conversation_callback: Callable
    ) -> str:
        """새 대화 시작 핸들러"""
        logger.info(f"[Handler] Starting new conversation: {session_id}")

        # 새 orchestrator 생성 (session_id 전달로 이벤트 로그 연결)
        orchestrator = ConversationOrchestrator(self.ai_manager, self.settings, session_id=session_id)
        self.active_conversations[session_id] = orchestrator
        self.session_metadata[session_id] = {
            'created_at': time.time(),
            'last_activity': time.time(),
            'topic': data.get("topic", "자유 주제")
        }

        # 설정 파싱
        config = self._parse_conversation_config(data)

        # 대화 루프를 백그라운드 태스크로 실행
        asyncio.create_task(
            run_conversation_callback(websocket, orchestrator, config, session_id)
        )

        return session_id

    async def _handle_user_intervene(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
        session_id: str,
        orchestrator: Optional[ConversationOrchestrator],
        run_conversation_callback: Callable
    ) -> None:
        """사용자 개입 핸들러"""
        if not orchestrator:
            logger.error(f"[Handler] No orchestrator for user_intervene! session_id: {session_id}")
            return

        message = data.get("content", "")
        file_ids = data.get("file_ids", [])
        images = []

        # 파일 컨텍스트 추가
        if file_ids:
            from app.routers.files import get_file_context, get_file_images
            file_context = get_file_context(file_ids)
            images = get_file_images(file_ids)
            if file_context:
                message = f"{message}\n\n{file_context}" if message else file_context

        orchestrator.user_intervene(message, images=images)
        await self.connection_manager.send_json(websocket, {
            "type": "user_intervention_ack",
            "content": data.get("content", ""),
            "has_files": len(file_ids) > 0,
            "has_images": len(images) > 0
        })
        logger.info(f"[Handler] User intervention processed for session: {session_id}")

    async def _handle_pause(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
        session_id: str,
        orchestrator: Optional[ConversationOrchestrator],
        run_conversation_callback: Callable
    ) -> None:
        """일시정지 핸들러"""
        logger.info(f"[Handler] Pause requested, session_id: {session_id}")

        if not orchestrator:
            logger.error(f"[Handler] No orchestrator for pause! session_id: {session_id}")
            await self.connection_manager.send_json(websocket, {
                "type": "error",
                "content": "세션을 찾을 수 없습니다."
            })
            return

        orchestrator.pause()
        logger.info(f"[Handler] Pause flag set: {orchestrator._pause_flag}")
        await self.connection_manager.send_json(websocket, {"type": "paused"})

    async def _handle_resume(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
        session_id: str,
        orchestrator: Optional[ConversationOrchestrator],
        run_conversation_callback: Callable
    ) -> None:
        """재개 핸들러"""
        logger.info(f"[Handler] Resume requested, session_id: {session_id}")

        if not orchestrator:
            logger.error(f"[Handler] No orchestrator for resume! session_id: {session_id}")
            await self.connection_manager.send_json(websocket, {
                "type": "error",
                "content": "세션을 찾을 수 없습니다."
            })
            return

        orchestrator.resume()
        logger.info(f"[Handler] Resume flag set, pause_flag: {orchestrator._pause_flag}")
        await self.connection_manager.send_json(websocket, {"type": "resumed"})

    async def _handle_stop(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
        session_id: str,
        orchestrator: Optional[ConversationOrchestrator],
        run_conversation_callback: Callable
    ) -> None:
        """대화 종료 핸들러"""
        debug_action(session_id, "STOP_REQUESTED", {
            "has_orchestrator": orchestrator is not None,
            "turn_count": getattr(orchestrator, '_turn_count', None) if orchestrator else None
        })
        logger.info(f"[Handler] Stop requested, session_id: {session_id}")

        if not orchestrator:
            debug_error(session_id, "STOP_NO_ORCHESTRATOR", "Orchestrator not found")
            logger.error(f"[Handler] No orchestrator for stop! session_id: {session_id}")
            await self.connection_manager.send_json(websocket, {
                "type": "error",
                "content": "세션을 찾을 수 없습니다."
            })
            return

        orchestrator.stop()
        debug_state(session_id, "stop_flag", False, True, "user requested stop")
        logger.info(f"[Handler] Stop flag set: {orchestrator._stop_flag}")
        debug_ws_send(session_id, "stopped", None)
        await self.connection_manager.send_json(websocket, {"type": "stopped"})

    async def _handle_set_speed(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
        session_id: str,
        orchestrator: Optional[ConversationOrchestrator],
        run_conversation_callback: Callable
    ) -> None:
        """속도 변경 핸들러"""
        if not orchestrator:
            logger.error(f"[Handler] No orchestrator for set_speed! session_id: {session_id}")
            return

        speed = ConversationSpeed(data.get("speed", "normal"))
        orchestrator.set_speed(speed)
        logger.info(f"[Handler] Speed changed to {speed.value} ({speed.delay_seconds}s)")
        await self.connection_manager.send_json(websocket, {
            "type": "speed_changed",
            "speed": speed.value
        })

    async def _handle_resume_conversation(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
        session_id: str,
        orchestrator: Optional[ConversationOrchestrator],
        run_conversation_callback: Callable
    ) -> str:
        """종료된 대화 재개 핸들러"""
        debug_system(session_id, "RESUME_CONVERSATION_START", {
            "has_existing_orchestrator": orchestrator is not None,
            "data_keys": list(data.keys())
        })
        logger.info(f"[Handler] ======= RESUME_CONVERSATION START =======")
        logger.info(f"[Handler] Resuming stopped conversation: {session_id}")
        logger.info(f"[Handler] Data keys: {data.keys()}")

        # 기존 에이전트 정보 저장 (재사용을 위해)
        existing_agents = data.get("existing_agents", [])
        debug_agent(session_id, "EXISTING_AGENTS_RECEIVED", {
            "count": len(existing_agents),
            "agents": [{"name": a.get("name"), "model": a.get("model")} for a in existing_agents]
        })
        logger.info(f"[Handler] Existing agents from client: {len(existing_agents)}")

        # 기존 orchestrator가 있으면 정리
        if orchestrator:
            debug_state(session_id, "old_orchestrator", "exists", "stopped_and_deleted", "creating new orchestrator")
            orchestrator.stop()
            if session_id in self.active_conversations:
                del self.active_conversations[session_id]

        # 새 orchestrator 생성 (session_id 전달로 이벤트 로그 연결)
        orchestrator = ConversationOrchestrator(self.ai_manager, self.settings, session_id=session_id)
        self.active_conversations[session_id] = orchestrator
        self.session_metadata[session_id] = {
            'created_at': time.time(),
            'last_activity': time.time(),
            'topic': data.get("topic", "자유 주제")
        }
        debug_system(session_id, "NEW_ORCHESTRATOR_CREATED", {"orchestrator_id": orchestrator._id})

        # 기존 대화 기록을 주제에 포함
        config = self._parse_resume_config(data, existing_agents)

        debug_system(session_id, "CONFIG_CREATED", {
            "topic_length": len(config.topic),
            "agent_count": config.agent_count,
            "models": [m.get("id") for m in (config.models or [])],
            "using_existing_agents": len(existing_agents) > 0
        })
        logger.info(f"[Handler] Config created: topic_len={len(config.topic)}, agent_count={config.agent_count}")
        logger.info(f"[Handler] Models: {config.models}")
        logger.info(f"[Handler] Using existing agents: {len(existing_agents) > 0}")

        # 대화 루프를 백그라운드 태스크로 실행
        logger.info(f"[Handler] Starting background task for conversation")
        task = asyncio.create_task(
            run_conversation_callback(websocket, orchestrator, config, session_id)
        )
        task.add_done_callback(
            lambda t: logger.info(f"[Handler] Background task completed: {t.exception() if t.exception() else 'OK'}")
        )
        logger.info(f"[Handler] ======= RESUME_CONVERSATION END =======")

        return session_id

    async def _handle_get_state(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
        session_id: str,
        orchestrator: Optional[ConversationOrchestrator],
        run_conversation_callback: Callable
    ) -> None:
        """현재 상태 조회 핸들러"""
        if orchestrator:
            state = orchestrator.get_state()
            await self.connection_manager.send_json(websocket, {
                "type": "state",
                "data": state
            })

    async def _handle_ping(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
        session_id: str,
        orchestrator: Optional[ConversationOrchestrator],
        run_conversation_callback: Callable
    ) -> None:
        """Ping 핸들러 (연결 유지)"""
        await self.connection_manager.send_json(websocket, {"type": "pong"})

    async def _handle_sync_events(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
        session_id: str,
        orchestrator: Optional[ConversationOrchestrator],
        run_conversation_callback: Callable
    ) -> None:
        """
        이벤트 동기화 핸들러 (Event Sourcing)

        누락된 이벤트를 클라이언트에게 전송
        프론트엔드에서 시퀀스 갭을 감지했을 때 호출
        """
        since_seq = data.get("since_seq", 0)

        if not orchestrator:
            logger.warning(f"[Handler] No orchestrator for sync_events, session_id: {session_id}")
            await self.connection_manager.send_json(websocket, {
                "type": "sync_events",
                "events": [],
                "error": "세션을 찾을 수 없습니다."
            })
            return

        # orchestrator에서 이벤트 로그 가져오기
        events = orchestrator.get_events_since(since_seq)

        logger.info(f"[Handler] Sync events: since_seq={since_seq}, returning {len(events)} events")

        await self.connection_manager.send_json(websocket, {
            "type": "sync_events",
            "events": events,
            "current_seq": orchestrator.get_event_log().current_seq if orchestrator.get_event_log() else 0
        })

    async def _handle_legacy_message(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
        session_id: str,
        orchestrator: Optional[ConversationOrchestrator],
        run_conversation_callback: Callable
    ) -> None:
        """기존 1:1 채팅 지원 (하위 호환)"""
        user_message = data.get("content", "")
        model = data.get("model", self.settings.default_model)

        await self.connection_manager.send_json(websocket, {
            "type": "user_message",
            "content": user_message,
            "sender": "user"
        })

        await self._stream_ai_response(websocket, user_message, model)

    async def _stream_ai_response(self, websocket: WebSocket, user_message: str, model: str):
        """Stream AI response to client (기존 1:1 채팅용)"""
        await self.connection_manager.send_json(websocket, {
            "type": "ai_start",
            "sender": "ai",
            "model": model
        })

        full_response = ""

        try:
            async for token in self.ai_manager.generate_stream(user_message, model):
                full_response += token
                await self.connection_manager.send_json(websocket, {
                    "type": "token",
                    "content": token
                })

            await self.connection_manager.send_json(websocket, {
                "type": "ai_complete",
                "content": full_response,
                "sender": "ai",
                "model": model
            })
        except Exception as e:
            logger.error(f"[Handler] Error streaming AI response: {e}")
            await self.connection_manager.send_json(websocket, {
                "type": "error",
                "content": str(e)
            })

    def _parse_conversation_config(self, data: Dict[str, Any]) -> ConversationConfig:
        """대화 설정 파싱"""
        # 안전 제한 설정 파싱
        limits_data = data.get("limits", {})
        limits = ConversationLimits(
            max_turns=limits_data.get("maxTurns", 100),
            max_cost=limits_data.get("maxCost", 1.0),
            max_minutes=limits_data.get("maxMinutes", 30),
            pause_on_inactive=limits_data.get("pauseOnInactive", True)
        )

        # 첨부 파일 처리
        file_ids = data.get("file_ids", [])
        initial_file_context = ""
        initial_images = []

        if file_ids:
            from app.routers.files import get_file_context, get_file_images
            initial_file_context = get_file_context(file_ids)
            initial_images = get_file_images(file_ids)
            logger.info(f"[Handler] Initial files: {len(file_ids)} files, {len(initial_images)} images")

        # 주제에 파일 컨텍스트 추가
        topic = data.get("topic", "자유 주제")
        if initial_file_context:
            topic = f"{topic}\n\n[첨부된 참고 자료]\n{initial_file_context}"

        return ConversationConfig(
            topic=topic,
            agent_count=data.get("agent_count", 2),
            speed=ConversationSpeed(data.get("speed", "normal")),
            auto_start=data.get("auto_start", True),
            models=data.get("models", None),
            limits=limits,
            initial_images=initial_images
        )

    def _parse_resume_config(self, data: Dict[str, Any], existing_agents: List[Dict] = None) -> ConversationConfig:
        """재개 대화 설정 파싱"""
        # 안전 제한 설정 파싱
        limits_data = data.get("limits", {})
        limits = ConversationLimits(
            max_turns=limits_data.get("maxTurns", 100),
            max_cost=limits_data.get("maxCost", 1.0),
            max_minutes=limits_data.get("maxMinutes", 30),
            pause_on_inactive=limits_data.get("pauseOnInactive", True)
        )

        # 파일 처리
        file_ids = data.get("file_ids", [])
        initial_images = []
        if file_ids:
            from app.routers.files import get_file_images
            initial_images = get_file_images(file_ids)

        # 기존 메시지에서 대화 기록 구성
        existing_messages = data.get("existing_messages", [])
        user_message = data.get("user_message", "")

        # 기존 대화 기록을 주제에 포함
        topic = data.get("topic", "자유 주제")
        if existing_messages:
            conversation_history = "\n\n[이전 대화 기록]\n"
            for msg in existing_messages[-10:]:  # 최근 10개 메시지만
                if msg.get("isUser"):
                    conversation_history += f"사용자: {msg.get('content', '')}\n"
                elif msg.get("agent"):
                    agent_name = msg.get("agent", {}).get("name", "AI")
                    content = msg.get('content', '')
                    if len(content) > 500:
                        conversation_history += f"{agent_name}: {content[:500]}...\n"
                    else:
                        conversation_history += f"{agent_name}: {content}\n"
            topic = f"{topic}{conversation_history}\n[사용자의 새 메시지]\n{user_message}"

        # 기존 에이전트 정보가 있으면 해당 모델들 사용
        models = data.get("models", None)
        agent_count = data.get("agent_count", 2)

        if existing_agents and len(existing_agents) > 0:
            # 기존 에이전트의 모델 정보 추출
            models = []
            for agent in existing_agents:
                model_id = agent.get("model", "")
                provider = "google" if "gemini" in model_id.lower() else "openai"
                models.append({"id": model_id, "provider": provider})
            agent_count = len(existing_agents)
            logger.info(f"[Handler] Using existing agent models: {models}")

        return ConversationConfig(
            topic=topic,
            agent_count=agent_count,
            speed=ConversationSpeed(data.get("speed", "normal")),
            auto_start=True,
            models=models,
            limits=limits,
            initial_images=initial_images,
            existing_agents=existing_agents or []
        )
