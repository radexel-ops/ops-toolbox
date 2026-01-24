"""
AI Infinite Chat - FastAPI Main Application
다중 AI 무한 대화 플랫폼

리팩토링 완료:
- WebSocket 메시지 핸들러를 handlers.py로 분리
- 세션 관리 로직 강화
- 에러 핸들링 개선
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
from app.websocket.handlers import WebSocketMessageHandler
from app.services.ai_manager import AIManager
from app.services.conversation_orchestrator import (
    ConversationOrchestrator,
    ConversationConfig,
)
from app.routers import chat, settings as settings_router, files as files_router


# Managers
connection_manager = ConnectionManager()
ai_manager: AIManager = None
message_handler: WebSocketMessageHandler = None

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
                orchestrator = active_conversations[session_id]
                orchestrator.stop()
                logger.info(f"[Cleanup] Orchestrator stopped for session: {session_id}")
            except Exception as e:
                logger.error(f"[Cleanup] Error stopping orchestrator: {e}")
            del active_conversations[session_id]

        if session_id in session_metadata:
            del session_metadata[session_id]

        logger.info(f"[Cleanup] Session removed ({reason}): {session_id}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    global ai_manager, message_handler

    # Startup
    settings = get_settings()
    ai_manager = AIManager(settings)

    # WebSocket 메시지 핸들러 초기화
    message_handler = WebSocketMessageHandler(
        connection_manager=connection_manager,
        ai_manager=ai_manager,
        settings=settings,
        active_conversations=active_conversations,
        session_metadata=session_metadata,
        session_lock=session_lock
    )

    print(f"AI Infinite Chat started on {settings.host}:{settings.port}")

    # 세션 정리 백그라운드 태스크 시작
    cleanup_task = asyncio.create_task(cleanup_stale_sessions())

    yield

    # Shutdown
    cleanup_task.cancel()
    # 모든 활성 세션 정리
    for session_id, orchestrator in list(active_conversations.items()):
        try:
            orchestrator.stop()
        except Exception as e:
            logger.error(f"[Shutdown] Error stopping orchestrator {session_id}: {e}")
    active_conversations.clear()
    session_metadata.clear()
    print("AI Infinite Chat shutting down...")


# Create FastAPI app
app = FastAPI(
    title="AI Infinite Chat",
    description="AI들의 무한 대화 플랫폼",
    version="0.3.0",  # 버전 업데이트
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
    return {
        "status": "ok",
        "message": "AI Infinite Chat API",
        "version": "0.3.0",
        "active_sessions": len(active_conversations)
    }


@app.get("/health")
async def health_check():
    """상세 헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "active_sessions": len(active_conversations),
        "active_connections": connection_manager.connection_count,
        "ai_providers": list(ai_manager.providers.keys()) if ai_manager else []
    }


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time AI-to-AI chat"""
    await connection_manager.connect(websocket)
    current_session_id = None  # 현재 연결의 세션 ID 추적

    try:
        while True:
            data = await websocket.receive_json()

            # 메시지 핸들러에 위임
            result = await message_handler.handle_message(
                websocket=websocket,
                data=data,
                run_conversation_callback=run_conversation
            )

            # 새 세션 시작 시 세션 ID 추적
            if result and data.get("type") in ("start_conversation", "resume_conversation"):
                current_session_id = result

    except WebSocketDisconnect:
        # 연결 해제 시 현재 세션의 orchestrator만 정리
        # (다른 연결에서 같은 세션을 제어할 수 있으므로 바로 삭제하지 않음)
        await connection_manager.disconnect(websocket)
        logger.info(f"[WS] Disconnected, session_id: {current_session_id}")
    except Exception as e:
        logger.error(f"[WS] Unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await connection_manager.disconnect(websocket)


async def run_conversation(
    websocket: WebSocket,
    orchestrator: ConversationOrchestrator,
    config: ConversationConfig,
    session_id: str
):
    """대화 루프 실행"""
    logger.info(f"[run_conversation] START - session: {session_id}")
    should_cleanup = False  # WebSocket 에러로 인한 강제 종료 시에만 정리

    try:
        event_count = 0
        async for event in orchestrator.start_conversation(
            config=config,
            on_message=lambda msg: None  # WebSocket으로 직접 전송
        ):
            # 연결 상태 먼저 확인
            if not connection_manager.is_connected(websocket):
                logger.info(f"[run_conversation] WebSocket disconnected, stopping orchestrator")
                orchestrator.stop()
                should_cleanup = True
                break

            event_count += 1
            event_type = event.get("type", "unknown")
            logger.debug(f"[run_conversation] Event {event_count}: {event_type}")
            try:
                await connection_manager.send_json(websocket, event)
                if event_type == "conversation_started":
                    logger.info(f"[run_conversation] conversation_started sent successfully")
            except (RuntimeError, Exception) as e:
                # WebSocket이 이미 닫힌 경우 - 세션 정리 필요
                if "websocket" in str(e).lower() or "close" in str(e).lower():
                    logger.info(f"[run_conversation] WebSocket closed, stopping orchestrator")
                else:
                    logger.error(f"[run_conversation] WebSocket error: {e}")
                orchestrator.stop()
                should_cleanup = True
                break

    except Exception as e:
        logger.error(f"[run_conversation] Error in session {session_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        should_cleanup = True  # 예외 발생 시 세션 정리
        try:
            await connection_manager.send_json(websocket, {
                "type": "error",
                "content": str(e)
            })
        except RuntimeError:
            pass  # WebSocket이 이미 닫힌 경우 무시
    finally:
        logger.info(f"[run_conversation] END - session: {session_id}, cleanup: {should_cleanup}")

        # 세션 활동 시간 업데이트 (timeout 정리 대상이 되도록)
        async with session_lock:
            if session_id in session_metadata:
                session_metadata[session_id]['last_activity'] = time.time()
                # 재개 가능 상태로 표시
                session_metadata[session_id]['resumable'] = True

        # WebSocket 에러나 예외 발생 시에만 즉시 정리
        # 자연스러운 종료(conversation_ended, limit_reached)는 세션 유지하여 재개 가능하게 함
        if should_cleanup:
            await cleanup_session(session_id, reason="error_or_disconnect")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
