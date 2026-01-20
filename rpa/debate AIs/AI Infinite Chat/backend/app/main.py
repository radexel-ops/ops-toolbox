"""
AI Infinite Chat - FastAPI Main Application
다중 AI 무한 대화 플랫폼
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
import time
from typing import Dict, Any

# Configure logging with DEBUG level for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from app.config import get_settings
from app.websocket.manager import ConnectionManager
from app.services.ai_manager import AIManager
from app.services.conversation_orchestrator import (
    ConversationOrchestrator,
    ConversationConfig,
    ConversationSpeed,
    ConversationLimits
)
from app.routers import chat, settings as settings_router, files as files_router


# Managers
connection_manager = ConnectionManager()
ai_manager: AIManager = None

# 세션 관리를 위한 Lock (동시성 제어)
session_lock = asyncio.Lock()

# Active conversations (session_id -> orchestrator)
active_conversations: Dict[str, ConversationOrchestrator] = {}
# Session metadata (session_id -> {created_at, last_activity})
session_metadata: Dict[str, Dict[str, Any]] = {}

# 세션 타임아웃 (30분)
SESSION_TIMEOUT_SECONDS = 30 * 60


async def cleanup_stale_sessions():
    """오래된 세션 정리 백그라운드 태스크"""
    while True:
        try:
            current_time = time.time()
            stale_sessions = []

            # list()로 복사하여 반복 중 수정 방지
            async with session_lock:
                for session_id, metadata in list(session_metadata.items()):
                    if current_time - metadata.get('last_activity', 0) > SESSION_TIMEOUT_SECONDS:
                        stale_sessions.append(session_id)

            for session_id in stale_sessions:
                await cleanup_session(session_id, reason="timeout")

            if stale_sessions:
                logger.info(f"[Cleanup] Cleaned up {len(stale_sessions)} stale sessions. Active: {len(active_conversations)}")

        except Exception as e:
            logger.error(f"[Cleanup] Error during cleanup: {e}")

        await asyncio.sleep(60)  # 1분마다 체크


async def cleanup_session(session_id: str, reason: str = "manual"):
    """세션 정리 헬퍼 함수"""
    async with session_lock:
        if session_id in active_conversations:
            try:
                active_conversations[session_id].stop()
            except Exception as e:
                logger.error(f"[Cleanup] Error stopping orchestrator: {e}")
            del active_conversations[session_id]

        if session_id in session_metadata:
            del session_metadata[session_id]

        logger.info(f"[Cleanup] Session removed ({reason}): {session_id}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    global ai_manager

    # Startup
    settings = get_settings()
    ai_manager = AIManager(settings)
    print(f"AI Infinite Chat started on {settings.host}:{settings.port}")

    # 세션 정리 백그라운드 태스크 시작
    cleanup_task = asyncio.create_task(cleanup_stale_sessions())

    yield

    # Shutdown
    cleanup_task.cancel()
    # 모든 활성 세션 정리
    for session_id, orchestrator in active_conversations.items():
        orchestrator.stop()
    active_conversations.clear()
    session_metadata.clear()
    print("AI Infinite Chat shutting down...")


# Create FastAPI app
app = FastAPI(
    title="AI Infinite Chat",
    description="AI들의 무한 대화 플랫폼",
    version="0.2.0",
    lifespan=lifespan
)

# CORS middleware
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 환경에서 모든 origin 허용
    allow_credentials=False,  # credentials와 wildcard origin은 함께 사용 불가
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(settings_router.router, prefix="/api", tags=["settings"])
app.include_router(files_router.router, prefix="/api", tags=["files"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "AI Infinite Chat API", "version": "0.2.0"}


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time AI-to-AI chat"""
    await connection_manager.connect(websocket)
    current_session_id = None  # 현재 연결의 세션 ID 추적

    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type", "")
            session_id = data.get("session_id")

            # 세션 ID로 orchestrator 조회
            orchestrator = active_conversations.get(session_id) if session_id else None
            logger.info(f"[WS] Received: {message_type}, session_id: {session_id}, orchestrator exists: {orchestrator is not None}")

            # 세션 활동 시간 업데이트
            if session_id and session_id in session_metadata:
                session_metadata[session_id]['last_activity'] = time.time()

            if message_type == "start_conversation":
                # 새 대화 시작
                current_session_id = session_id
                orchestrator = ConversationOrchestrator(ai_manager, settings)
                active_conversations[session_id] = orchestrator
                session_metadata[session_id] = {
                    'created_at': time.time(),
                    'last_activity': time.time(),
                    'topic': data.get("topic", "자유 주제")
                }
                logger.info(f"[WS] Created orchestrator for session: {session_id}")

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
                    logger.info(f"[WS] Initial files: {len(file_ids)} files, {len(initial_images)} images")

                # 주제에 파일 컨텍스트 추가
                topic = data.get("topic", "자유 주제")
                if initial_file_context:
                    topic = f"{topic}\n\n[첨부된 참고 자료]\n{initial_file_context}"

                config = ConversationConfig(
                    topic=topic,
                    agent_count=data.get("agent_count", 2),
                    speed=ConversationSpeed(data.get("speed", "normal")),
                    auto_start=data.get("auto_start", True),
                    models=data.get("models", None),
                    limits=limits,
                    initial_images=initial_images
                )

                # 대화 루프를 백그라운드 태스크로 실행
                asyncio.create_task(
                    run_conversation(websocket, orchestrator, config, session_id)
                )

            elif message_type == "user_intervene":
                # 사용자 개입
                if orchestrator:
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
                    await connection_manager.send_json(websocket, {
                        "type": "user_intervention_ack",
                        "content": data.get("content", ""),
                        "has_files": len(file_ids) > 0,
                        "has_images": len(images) > 0
                    })
                else:
                    logger.error(f"[WS] ERROR: No orchestrator for user_intervene! session_id: {session_id}")

            elif message_type == "pause":
                # 일시정지
                logger.info(f"[WS] Pause requested, session_id: {session_id}, orchestrator: {orchestrator}")
                if orchestrator:
                    orchestrator.pause()
                    logger.info(f"[WS] Pause flag set: {orchestrator._pause_flag}")
                    await connection_manager.send_json(websocket, {
                        "type": "paused"
                    })
                else:
                    logger.error(f"[WS] ERROR: No orchestrator for pause! session_id: {session_id}")

            elif message_type == "resume":
                # 재개
                if orchestrator:
                    orchestrator.resume()
                    await connection_manager.send_json(websocket, {
                        "type": "resumed"
                    })
                else:
                    logger.error(f"[WS] ERROR: No orchestrator for resume! session_id: {session_id}")

            elif message_type == "stop":
                # 대화 종료
                logger.info(f"[WS] Stop requested, session_id: {session_id}, orchestrator: {orchestrator}")
                if orchestrator:
                    orchestrator.stop()
                    logger.info(f"[WS] Stop flag set: {orchestrator._stop_flag}")
                    await connection_manager.send_json(websocket, {
                        "type": "stopped"
                    })
                else:
                    logger.error(f"[WS] ERROR: No orchestrator for stop! session_id: {session_id}")

            elif message_type == "set_speed":
                # 속도 변경
                if orchestrator:
                    speed = ConversationSpeed(data.get("speed", "normal"))
                    orchestrator.set_speed(speed)
                    logger.info(f"[Speed Changed] {speed.value} ({speed.delay_seconds}s)")
                    await connection_manager.send_json(websocket, {
                        "type": "speed_changed",
                        "speed": speed.value
                    })
                else:
                    logger.error(f"[WS] ERROR: No orchestrator for set_speed! session_id: {session_id}")

            elif message_type == "resume_conversation":
                # 종료된 대화 재개
                current_session_id = session_id
                logger.info(f"[WS] ======= RESUME_CONVERSATION START =======")
                logger.info(f"[WS] Resuming stopped conversation: {session_id}")
                logger.info(f"[WS] Data keys: {data.keys()}")

                # 기존 orchestrator가 있으면 정리
                if orchestrator:
                    orchestrator.stop()
                    if session_id in active_conversations:
                        del active_conversations[session_id]

                # 새 orchestrator 생성
                orchestrator = ConversationOrchestrator(ai_manager, settings)
                active_conversations[session_id] = orchestrator
                session_metadata[session_id] = {
                    'created_at': time.time(),
                    'last_activity': time.time(),
                    'topic': data.get("topic", "자유 주제")
                }

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
                            conversation_history += f"{agent_name}: {msg.get('content', '')[:500]}...\n" if len(msg.get('content', '')) > 500 else f"{agent_name}: {msg.get('content', '')}\n"
                    topic = f"{topic}{conversation_history}\n[사용자의 새 메시지]\n{user_message}"

                config = ConversationConfig(
                    topic=topic,
                    agent_count=data.get("agent_count", 2),
                    speed=ConversationSpeed(data.get("speed", "normal")),
                    auto_start=True,
                    models=data.get("models", None),
                    limits=limits,
                    initial_images=initial_images
                )

                logger.info(f"[WS] Config created: topic_len={len(topic)}, agent_count={config.agent_count}")
                logger.info(f"[WS] Models: {config.models}")

                # 대화 루프를 백그라운드 태스크로 실행
                logger.info(f"[WS] Starting background task for conversation")
                task = asyncio.create_task(
                    run_conversation(websocket, orchestrator, config, session_id)
                )
                task.add_done_callback(lambda t: logger.info(f"[WS] Background task completed: {t.exception() if t.exception() else 'OK'}"))
                logger.info(f"[WS] ======= RESUME_CONVERSATION END =======")

            elif message_type == "get_state":
                # 현재 상태 조회
                if orchestrator:
                    state = orchestrator.get_state()
                    await connection_manager.send_json(websocket, {
                        "type": "state",
                        "data": state
                    })

            elif message_type == "ping":
                await connection_manager.send_json(websocket, {"type": "pong"})

            # 기존 1:1 채팅 지원 (하위 호환)
            elif message_type == "message":
                user_message = data.get("content", "")
                model = data.get("model", settings.default_model)

                await connection_manager.send_json(websocket, {
                    "type": "user_message",
                    "content": user_message,
                    "sender": "user"
                })

                await stream_ai_response(websocket, user_message, model)

    except WebSocketDisconnect:
        # 연결 해제 시 현재 세션의 orchestrator만 정리
        # (다른 연결에서 같은 세션을 제어할 수 있으므로 바로 삭제하지 않음)
        await connection_manager.disconnect(websocket)
        logger.info(f"[WS] Disconnected, session_id: {current_session_id}")


async def run_conversation(
    websocket: WebSocket,
    orchestrator: ConversationOrchestrator,
    config: ConversationConfig,
    session_id: str
):
    """대화 루프 실행"""
    logger.info(f"[run_conversation] START - session: {session_id}")
    try:
        event_count = 0
        async for event in orchestrator.start_conversation(
            config=config,
            on_message=lambda msg: None  # WebSocket으로 직접 전송
        ):
            event_count += 1
            event_type = event.get("type", "unknown")
            logger.debug(f"[run_conversation] Event {event_count}: {event_type}")
            try:
                await connection_manager.send_json(websocket, event)
                if event_type == "conversation_started":
                    logger.info(f"[run_conversation] conversation_started sent successfully")
            except RuntimeError as e:
                # WebSocket이 이미 닫힌 경우
                logger.error(f"[run_conversation] WebSocket error: {e}")
                orchestrator.stop()
                break

    except Exception as e:
        logger.error(f"[run_conversation] Error in session {session_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        try:
            await connection_manager.send_json(websocket, {
                "type": "error",
                "content": str(e)
            })
        except RuntimeError:
            pass  # WebSocket이 이미 닫힌 경우 무시
    finally:
        logger.info(f"[run_conversation] END - session: {session_id}")
        # 대화 종료 시 세션 완전 정리 (메모리 누수 방지)
        await cleanup_session(session_id, reason="conversation_ended")


async def stream_ai_response(websocket: WebSocket, user_message: str, model: str):
    """Stream AI response to client (기존 1:1 채팅용)"""

    await connection_manager.send_json(websocket, {
        "type": "ai_start",
        "sender": "ai",
        "model": model
    })

    full_response = ""

    try:
        async for token in ai_manager.generate_stream(user_message, model):
            full_response += token
            await connection_manager.send_json(websocket, {
                "type": "token",
                "content": token
            })

        await connection_manager.send_json(websocket, {
            "type": "ai_complete",
            "content": full_response,
            "sender": "ai",
            "model": model
        })

    except Exception as e:
        await connection_manager.send_json(websocket, {
            "type": "error",
            "content": str(e)
        })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
