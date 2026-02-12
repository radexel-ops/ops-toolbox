# 09. Module Registry - VibeOps

> **문서 목적**: 공유 모듈 카탈로그. 코드 작성 전 반드시 확인.
> **상태**: LIVING DOCUMENT - 새 모듈 추가 시 업데이트 필수

---

## 0. 사용 규칙

### 필수 확인
**코드 작성 전 이 문서를 확인하라.** 이미 존재하는 모듈을 재구현하는 것은 **기술부채의 1등 원인**이다.

### 위반 시
- PR 리뷰에서 반려
- 중복 코드 발견 시 즉시 리팩토링

---

## 1. Backend 모듈

### 1.1 Services

| 모듈 | 경로 | 용도 |
|------|------|------|
| **DatabaseService** | `backend/app/services/database_service.py` | SQLite 데이터베이스 접근 |
| **AuthService** | `backend/app/services/auth_service.py` | 인증, 세션 관리 |
| **BridgeService** | `backend/app/services/bridge_service.py` | 웹-터미널 연결 |
| **AgentService** | `backend/app/services/agent_service.py` | 에이전트 생명주기 관리 |
| **NotificationService** | `backend/app/services/notification_service.py` | 알림 (Slack 등) |

### 1.2 Database 접근

```python
# ✅ 올바른 사용
from app.services.database_service import db_service

users = await db_service.get_users()
await db_service.create_user(data)

# ❌ 금지
import sqlite3
conn = sqlite3.connect("vibeops.db")  # 직접 연결 금지
```

### 1.3 인증

```python
# ✅ 올바른 사용
from app.services.auth_service import auth_service

user = await auth_service.authenticate(username, password)
token = auth_service.create_token(user_id)
verified = auth_service.verify_token(token)

# ❌ 금지
import jwt
jwt.encode(...)  # 직접 JWT 생성 금지
```

---

## 2. Frontend 모듈

### 2.1 JavaScript 모듈

| 모듈 | 경로 | 용도 |
|------|------|------|
| **BridgeClient** | `frontend/js/bridge-client.js` | WebSocket 연결 |
| **ApiClient** | `frontend/js/api.js` | REST API 호출 |
| **ChatUI** | `frontend/js/components/chat.js` | 채팅 인터페이스 |
| **DashboardUI** | `frontend/js/components/dashboard.js` | 대시보드 |

### 2.2 API 호출

```javascript
// ✅ 올바른 사용
import { api } from './api.js';

const agents = await api.get('/agents');
await api.post('/agents', { name: 'new-agent' });

// ❌ 금지
fetch('/api/agents')  // 직접 fetch 금지 (에러 핸들링, 토큰 누락)
```

### 2.3 WebSocket

```javascript
// ✅ 올바른 사용
import { BridgeClient } from './bridge-client.js';

const bridge = new BridgeClient(sessionId);
bridge.connect();
bridge.sendCommand('명령어');

// ❌ 금지
new WebSocket('ws://...')  // 직접 WebSocket 생성 금지
```

---

## 3. Agents 모듈

### 3.1 Base Classes

| 모듈 | 경로 | 용도 |
|------|------|------|
| **AgentBase** | `agents/base/agent_base.py` | 모든 에이전트의 베이스 클래스 |

### 3.2 새 에이전트 생성 규칙

```python
# ✅ 올바른 사용 - AgentBase 상속
from agents.base.agent_base import AgentBase

class MyAgent(AgentBase):
    def __init__(self):
        super().__init__("my_agent")

    async def execute(self, command: str = None) -> dict:
        # 구현
        pass

    async def health_check(self) -> bool:
        return True

# ❌ 금지 - 베이스 클래스 없이 직접 구현
class MyAgent:  # AgentBase 상속 안 함
    pass
```

---

## 4. Bridge 모듈

### 4.1 컴포넌트

| 모듈 | 경로 | 용도 |
|------|------|------|
| **BridgeServer** | `bridge/bridge_server.py` | WebSocket 서버 |
| **CommandQueue** | `bridge/command_queue.py` | 명령어 큐 |
| **TmuxController** | `bridge/tmux_controller.py` | Tmux 세션 제어 |
| **MessageTypes** | `bridge/message_types.py` | 메시지 타입 정의 |

### 4.2 Tmux 제어

```python
# ✅ 올바른 사용
from bridge.tmux_controller import TmuxController

tmux = TmuxController()
await tmux.execute("명령어", target_window="pm")
windows = await tmux.list_windows()

# ❌ 금지
import subprocess
subprocess.run(["tmux", "send-keys", ...])  # 직접 subprocess 금지
```

---

## 5. Utilities

### 5.1 공통 유틸리티

| 모듈 | 경로 | 용도 |
|------|------|------|
| **Logger** | `backend/app/utils/logger.py` | 로깅 |
| **Config** | `backend/app/config.py` | 설정 관리 |
| **Helpers** | `backend/app/utils/helpers.py` | 공통 헬퍼 함수 |

### 5.2 로깅

```python
# ✅ 올바른 사용
from app.utils.logger import get_logger

logger = get_logger(__name__)
logger.info("Processing")
logger.error("Error", exc_info=True)

# ❌ 금지
print("Debug message")  # print 금지
import logging; logging.info(...)  # 직접 logging 금지
```

### 5.3 설정

```python
# ✅ 올바른 사용
from app.config import settings

db_path = settings.DATABASE_PATH
debug = settings.DEBUG

# ❌ 금지
import os
db_path = os.getenv("DATABASE_PATH")  # 직접 os.getenv 금지
```

---

## 6. CSS 변수

### 6.1 색상

```css
/* frontend/css/variables.css */
:root {
    /* Primary */
    --color-primary: #2563eb;
    --color-primary-hover: #1d4ed8;

    /* Background */
    --color-bg: #ffffff;
    --color-bg-secondary: #f3f4f6;

    /* Text */
    --color-text: #111827;
    --color-text-secondary: #6b7280;

    /* Status */
    --color-success: #10b981;
    --color-warning: #f59e0b;
    --color-error: #ef4444;

    /* Border */
    --color-border: #e5e7eb;
}
```

### 6.2 사용 규칙

```css
/* ✅ 올바른 사용 */
.button {
    background: var(--color-primary);
    color: white;
}

/* ❌ 금지 */
.button {
    background: #2563eb;  /* 하드코딩 금지 */
}
```

---

## 7. 모듈 추가 절차

새 공유 모듈을 만들 때:

1. **검토**: 기존 모듈로 해결 가능한지 확인
2. **설계**: 재사용성 고려한 인터페이스 설계
3. **구현**: 적절한 위치에 모듈 생성
4. **문서화**: 이 문서에 모듈 정보 추가
5. **리뷰**: PR에서 팀원 리뷰

---

## 8. 변경 이력

| 날짜 | 변경 내용 | 작성자 |
|------|----------|--------|
| 2026-02-10 | 초기 모듈 카탈로그 작성 | - |

---

*Last Updated: 2026-02-10*
