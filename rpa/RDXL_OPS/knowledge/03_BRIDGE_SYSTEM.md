# 03. Bridge System - VibeOps

> **문서 목적**: 웹 대시보드와 서버 터미널을 연결하는 브릿지 시스템의 상세 설계입니다.

---

## 1. 개요

### 1.1 브릿지 시스템이란?

**"웹에서 말하면, 서버 속 AI가 움직인다"**

브릿지 시스템은 사용자의 웹 브라우저와 서버 내부의 터미널(Claude Code가 실행되는 환경)을 실시간으로 연결하는 중계 시스템입니다.

### 1.2 핵심 기능

| 기능 | 설명 |
|------|------|
| **실시간 연결** | WebSocket을 통한 양방향 통신 |
| **명령 전달** | 웹 → 서버 터미널로 명령 전달 |
| **결과 스트리밍** | 서버 → 웹으로 실시간 결과 전송 |
| **세션 관리** | 다중 사용자 세션 지원 |

---

## 2. 아키텍처

### 2.1 전체 흐름

```
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│                 │          │                 │          │                 │
│   Web Browser   │◄────────►│  Bridge Server  │◄────────►│  Tmux Session   │
│   (Frontend)    │ WebSocket│   (FastAPI)     │  Stdin/  │  (Claude Code)  │
│                 │          │                 │  Stdout  │                 │
└─────────────────┘          └─────────────────┘          └─────────────────┘
```

### 2.2 컴포넌트

```
bridge/
├── __init__.py
├── bridge_server.py      # WebSocket 서버
├── command_queue.py      # 명령어 큐 관리
├── session_manager.py    # 사용자 세션 관리
├── tmux_controller.py    # Tmux 세션 제어
└── message_types.py      # 메시지 타입 정의
```

---

## 3. 메시지 프로토콜

### 3.1 메시지 타입

```python
# message_types.py

from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any

class MessageType(str, Enum):
    # Client → Server
    COMMAND = "command"           # 사용자 명령
    PING = "ping"                 # 연결 확인

    # Server → Client
    RESPONSE = "response"         # 명령 응답
    STREAM = "stream"             # 스트리밍 데이터
    STATUS = "status"             # 상태 업데이트
    ERROR = "error"               # 에러
    PONG = "pong"                 # Ping 응답

class BridgeMessage(BaseModel):
    type: MessageType
    payload: Any
    timestamp: datetime = datetime.now()
    session_id: Optional[str] = None
```

### 3.2 메시지 예시

**명령 전송 (Client → Server)**
```json
{
    "type": "command",
    "payload": {
        "text": "이번 주 야근자 명단 뽑아줘",
        "target_agent": "pm"
    },
    "timestamp": "2026-02-10T14:30:00Z",
    "session_id": "user123"
}
```

**스트리밍 응답 (Server → Client)**
```json
{
    "type": "stream",
    "payload": {
        "status": "processing",
        "message": "[진행중] 더존 시스템 접속 중...",
        "progress": 30
    },
    "timestamp": "2026-02-10T14:30:05Z",
    "session_id": "user123"
}
```

**완료 응답 (Server → Client)**
```json
{
    "type": "response",
    "payload": {
        "status": "completed",
        "result": {
            "type": "table",
            "data": [
                {"name": "김대리", "date": "2026-02-09", "hours": 3},
                {"name": "박과장", "date": "2026-02-10", "hours": 2}
            ]
        }
    },
    "timestamp": "2026-02-10T14:30:15Z",
    "session_id": "user123"
}
```

---

## 4. 핵심 모듈 설계

### 4.1 Bridge Server

```python
# bridge_server.py

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict
import asyncio

class BridgeServer:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self.command_queue = CommandQueue()
        self.tmux = TmuxController()

    async def connect(self, websocket: WebSocket, session_id: str):
        """새 WebSocket 연결 처리"""
        await websocket.accept()
        self.connections[session_id] = websocket

    async def disconnect(self, session_id: str):
        """연결 해제"""
        if session_id in self.connections:
            del self.connections[session_id]

    async def handle_message(self, session_id: str, message: BridgeMessage):
        """수신 메시지 처리"""
        if message.type == MessageType.COMMAND:
            await self.process_command(session_id, message.payload)
        elif message.type == MessageType.PING:
            await self.send_pong(session_id)

    async def process_command(self, session_id: str, payload: dict):
        """명령 처리"""
        # 1. 명령 큐에 등록
        task_id = await self.command_queue.enqueue(payload)

        # 2. 진행 상태 알림
        await self.send_status(session_id, "processing", "명령 처리 중...")

        # 3. Tmux 세션에 명령 전달
        result = await self.tmux.execute(payload['text'], payload.get('target_agent', 'pm'))

        # 4. 결과 전송
        await self.send_response(session_id, result)

    async def send_response(self, session_id: str, result: Any):
        """응답 전송"""
        if session_id in self.connections:
            message = BridgeMessage(
                type=MessageType.RESPONSE,
                payload=result,
                session_id=session_id
            )
            await self.connections[session_id].send_json(message.dict())
```

### 4.2 Tmux Controller

```python
# tmux_controller.py

import subprocess
import asyncio

class TmuxController:
    def __init__(self, session_name: str = "vibeops"):
        self.session_name = session_name

    async def execute(self, command: str, target_window: str = "pm") -> dict:
        """
        Tmux 세션의 특정 윈도우에 명령 전달
        """
        # 명령을 Tmux 윈도우에 전송
        tmux_cmd = f"tmux send-keys -t {self.session_name}:{target_window} '{command}' Enter"

        process = await asyncio.create_subprocess_shell(
            tmux_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        # 출력 캡처 (별도 메커니즘 필요)
        output = await self._capture_output(target_window)

        return {
            "status": "completed" if process.returncode == 0 else "error",
            "output": output
        }

    async def _capture_output(self, window: str) -> str:
        """Tmux 윈도우 출력 캡처"""
        capture_cmd = f"tmux capture-pane -t {self.session_name}:{window} -p"
        process = await asyncio.create_subprocess_shell(
            capture_cmd,
            stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        return stdout.decode()

    async def create_window(self, window_name: str):
        """새 Tmux 윈도우 생성"""
        cmd = f"tmux new-window -t {self.session_name} -n {window_name}"
        await asyncio.create_subprocess_shell(cmd)

    async def list_windows(self) -> list:
        """윈도우 목록 조회"""
        cmd = f"tmux list-windows -t {self.session_name} -F '#I:#W'"
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        return stdout.decode().strip().split('\n')
```

### 4.3 Command Queue

```python
# command_queue.py

import asyncio
from collections import deque
from datetime import datetime
from uuid import uuid4

class CommandQueue:
    def __init__(self, max_size: int = 100):
        self.queue = deque(maxlen=max_size)
        self.history = []

    async def enqueue(self, payload: dict) -> str:
        """명령 큐에 추가"""
        task_id = str(uuid4())
        task = {
            "id": task_id,
            "payload": payload,
            "status": "pending",
            "created_at": datetime.now(),
            "completed_at": None
        }
        self.queue.append(task)
        return task_id

    async def dequeue(self) -> dict:
        """큐에서 다음 명령 가져오기"""
        if self.queue:
            return self.queue.popleft()
        return None

    async def mark_completed(self, task_id: str, result: Any):
        """작업 완료 처리"""
        for task in self.history:
            if task["id"] == task_id:
                task["status"] = "completed"
                task["completed_at"] = datetime.now()
                task["result"] = result
                break
```

---

## 5. WebSocket 엔드포인트

```python
# routers/bridge.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from ..services.bridge_service import BridgeServer

router = APIRouter(prefix="/bridge", tags=["bridge"])
bridge = BridgeServer()

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket 연결 엔드포인트"""
    await bridge.connect(websocket, session_id)

    try:
        while True:
            # 메시지 수신
            data = await websocket.receive_json()
            message = BridgeMessage(**data)

            # 메시지 처리
            await bridge.handle_message(session_id, message)

    except WebSocketDisconnect:
        await bridge.disconnect(session_id)
```

---

## 6. Frontend 연동

### 6.1 JavaScript WebSocket 클라이언트

```javascript
// js/bridge-client.js

class BridgeClient {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.ws = null;
        this.handlers = {};
    }

    connect() {
        const wsUrl = `ws://${window.location.host}/bridge/ws/${this.sessionId}`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('Bridge connected');
            this.startHeartbeat();
        };

        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
        };

        this.ws.onclose = () => {
            console.log('Bridge disconnected');
            // 자동 재연결
            setTimeout(() => this.connect(), 3000);
        };
    }

    handleMessage(message) {
        const handler = this.handlers[message.type];
        if (handler) {
            handler(message.payload);
        }
    }

    on(type, handler) {
        this.handlers[type] = handler;
    }

    sendCommand(text, targetAgent = 'pm') {
        const message = {
            type: 'command',
            payload: { text, target_agent: targetAgent },
            timestamp: new Date().toISOString(),
            session_id: this.sessionId
        };
        this.ws.send(JSON.stringify(message));
    }

    startHeartbeat() {
        setInterval(() => {
            if (this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    }
}

// 사용 예시
const bridge = new BridgeClient('user123');
bridge.connect();

bridge.on('stream', (payload) => {
    console.log('진행:', payload.message);
    updateProgress(payload.progress);
});

bridge.on('response', (payload) => {
    console.log('완료:', payload.result);
    displayResult(payload.result);
});

// 명령 전송
bridge.sendCommand('이번 주 야근자 명단 뽑아줘');
```

---

## 7. 보안 고려사항

### 7.1 인증
- WebSocket 연결 시 토큰 검증
- 세션 타임아웃 설정

### 7.2 입력 검증
- 명령어 길이 제한
- 위험한 명령어 필터링

### 7.3 Rate Limiting
- 연결당 명령 횟수 제한
- 동시 연결 수 제한

---

## 8. 모니터링

### 8.1 메트릭
- 활성 연결 수
- 명령 처리 시간
- 에러율

### 8.2 로깅
- 모든 명령/응답 기록
- 에러 상세 로그

---

*Last Updated: 2026-02-10*
