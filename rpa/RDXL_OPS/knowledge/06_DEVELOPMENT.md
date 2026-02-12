# 06. Development Guide - VibeOps

> **문서 목적**: 개발 환경 설정, 코딩 컨벤션, 개발 워크플로우를 정의합니다.

---

## 1. 개발 환경 설정

### 1.1 로컬 개발 환경

```bash
# 1. 프로젝트 클론
git clone https://github.com/YOUR_ORG/RDXL_OPS.git
cd RDXL_OPS

# 2. Python 가상환경 생성
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# 3. 의존성 설치
pip install -r backend/requirements.txt

# 4. 환경변수 설정
cp .env.example .env
# .env 파일 편집

# 5. 개발 서버 실행
cd backend
uvicorn app.main:app --reload --port 8000
```

### 1.2 권장 IDE

| IDE | 설정 |
|-----|------|
| **VS Code** | Python, Pylance, Black Formatter 확장 |
| **PyCharm** | Professional 권장 (FastAPI 지원) |

### 1.3 VS Code 설정

```json
// .vscode/settings.json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/venv/Scripts/python.exe",
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "editor.formatOnSave": true,
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter"
    }
}
```

---

## 2. 코딩 컨벤션

### 2.1 Python 스타일 가이드

| 항목 | 규칙 |
|------|------|
| **스타일** | PEP 8 준수 |
| **포맷터** | Black (line-length=100) |
| **린터** | Pylint, flake8 |
| **타입힌트** | 모든 함수에 필수 |
| **독스트링** | Google 스타일 |

### 2.2 예시 코드

```python
"""
모듈 설명

이 모듈은 사용자 관련 서비스를 제공합니다.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class User(BaseModel):
    """사용자 모델

    Attributes:
        id: 사용자 고유 ID
        name: 사용자 이름
        email: 이메일 주소
        created_at: 생성 일시
    """
    id: int
    name: str
    email: str
    created_at: datetime


async def get_user_by_id(user_id: int) -> Optional[User]:
    """ID로 사용자 조회

    Args:
        user_id: 조회할 사용자 ID

    Returns:
        User 객체 또는 None (미존재 시)

    Raises:
        DatabaseError: DB 연결 실패 시
    """
    # 구현
    pass


async def list_users(
    limit: int = 10,
    offset: int = 0,
    active_only: bool = True
) -> List[User]:
    """사용자 목록 조회

    Args:
        limit: 최대 조회 수
        offset: 시작 위치
        active_only: 활성 사용자만 조회 여부

    Returns:
        User 목록
    """
    # 구현
    pass
```

### 2.3 네이밍 규칙

| 대상 | 규칙 | 예시 |
|------|------|------|
| **파일** | snake_case | `user_service.py` |
| **클래스** | PascalCase | `UserService` |
| **함수** | snake_case | `get_user_by_id` |
| **상수** | UPPER_SNAKE | `MAX_CONNECTIONS` |
| **변수** | snake_case | `user_count` |
| **Private** | _prefix | `_internal_method` |

---

## 3. 프로젝트 구조

### 3.1 Backend 구조

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 앱 진입점
│   ├── config.py            # 설정 관리
│   ├── dependencies.py      # 의존성 주입
│   │
│   ├── routers/             # API 라우터
│   │   ├── __init__.py
│   │   ├── auth.py          # 인증 API
│   │   ├── bridge.py        # 브릿지 API (WebSocket)
│   │   ├── agents.py        # 에이전트 관리 API
│   │   └── tasks.py         # 작업 관리 API
│   │
│   ├── services/            # 비즈니스 로직
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── bridge_service.py
│   │   ├── agent_service.py
│   │   └── database_service.py
│   │
│   ├── models/              # 데이터 모델
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── agent.py
│   │   └── task.py
│   │
│   └── utils/               # 유틸리티
│       ├── __init__.py
│       ├── logger.py
│       └── helpers.py
│
├── tests/                   # 테스트
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   └── test_agents.py
│
├── requirements.txt
├── Dockerfile
└── pytest.ini
```

### 3.2 Frontend 구조

```
frontend/
├── index.html               # 메인 HTML
├── css/
│   ├── main.css            # 메인 스타일
│   ├── variables.css       # CSS 변수
│   └── components/         # 컴포넌트별 스타일
│       ├── chat.css
│       └── dashboard.css
├── js/
│   ├── main.js             # 메인 스크립트
│   ├── bridge-client.js    # WebSocket 클라이언트
│   ├── api.js              # API 호출
│   └── components/         # UI 컴포넌트
│       ├── chat.js
│       └── dashboard.js
└── assets/
    └── images/
```

---

## 4. API 설계 규칙

### 4.1 RESTful 규칙

| HTTP Method | 용도 | 예시 |
|-------------|------|------|
| GET | 조회 | `GET /api/agents` |
| POST | 생성 | `POST /api/agents` |
| PUT | 전체 수정 | `PUT /api/agents/{id}` |
| PATCH | 부분 수정 | `PATCH /api/agents/{id}` |
| DELETE | 삭제 | `DELETE /api/agents/{id}` |

### 4.2 응답 형식

```python
# 성공 응답
{
    "success": true,
    "data": { ... },
    "message": "조회 성공"
}

# 에러 응답
{
    "success": false,
    "error": {
        "code": "AGENT_NOT_FOUND",
        "message": "에이전트를 찾을 수 없습니다"
    }
}

# 목록 응답
{
    "success": true,
    "data": [ ... ],
    "pagination": {
        "total": 100,
        "page": 1,
        "limit": 10
    }
}
```

### 4.3 에러 코드

| 코드 | HTTP | 설명 |
|------|------|------|
| `AUTH_REQUIRED` | 401 | 인증 필요 |
| `FORBIDDEN` | 403 | 권한 없음 |
| `NOT_FOUND` | 404 | 리소스 없음 |
| `VALIDATION_ERROR` | 422 | 입력값 오류 |
| `INTERNAL_ERROR` | 500 | 서버 오류 |

---

## 5. Git 워크플로우

### 5.1 브랜치 전략

```
main          ← 프로덕션 배포
  └── develop ← 개발 통합
        ├── feature/xxx  ← 기능 개발
        ├── bugfix/xxx   ← 버그 수정
        └── hotfix/xxx   ← 긴급 수정
```

### 5.2 커밋 메시지

```
<type>: <subject>

<body>

<footer>
```

| Type | 설명 |
|------|------|
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `docs` | 문서 |
| `style` | 포맷팅 |
| `refactor` | 리팩토링 |
| `test` | 테스트 |
| `chore` | 기타 |

**예시:**
```
feat: 뉴스 에이전트 슬랙 연동 추가

- Slack Webhook 연동 구현
- 뉴스 요약 포맷 개선
- 에러 핸들링 추가

Closes #123
```

### 5.3 PR 템플릿

```markdown
## 변경 사항
-

## 테스트
- [ ] 로컬 테스트 완료
- [ ] 단위 테스트 통과

## 스크린샷 (UI 변경 시)

## 관련 이슈
Closes #
```

---

## 6. 테스트

### 6.1 테스트 구조

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}
```

```python
# tests/test_agents.py
def test_list_agents(client):
    response = client.get("/api/agents")
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_create_agent(client, auth_headers):
    response = client.post(
        "/api/agents",
        headers=auth_headers,
        json={"name": "test-agent", "type": "custom"}
    )
    assert response.status_code == 201
```

### 6.2 테스트 실행

```bash
# 전체 테스트
pytest

# 특정 파일
pytest tests/test_agents.py

# 커버리지
pytest --cov=app --cov-report=html
```

---

## 7. 디버깅

### 7.1 로깅

```python
# app/utils/logger.py
import logging

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

# 사용
logger = get_logger(__name__)
logger.info("Processing request")
logger.error("Error occurred", exc_info=True)
```

### 7.2 API 문서

FastAPI 자동 문서:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

*Last Updated: 2026-02-10*
