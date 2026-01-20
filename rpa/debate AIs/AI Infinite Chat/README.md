# AI Infinite Chat

AI들이 사용자가 던진 주제에 대해 무제한으로 대화하는 웹/모바일 앱

## 기술 스택

- **Backend**: Python FastAPI + WebSocket
- **Frontend**: React + Vite
- **AI**: OpenAI GPT (Phase 1), Claude, Gemini, Grok (Phase 2)

## 빠른 시작

### 1. 백엔드 설정

```bash
cd backend

# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일을 열어서 OPENAI_API_KEY 설정

# 서버 실행
uvicorn app.main:app --reload
```

### 2. 프론트엔드 설정

```bash
cd frontend

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

### 3. 접속

브라우저에서 `http://localhost:5173` 접속

## 프로젝트 구조

```
AI Infinite Chat/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 앱
│   │   ├── config.py        # 설정
│   │   ├── routers/         # API 라우터
│   │   ├── services/        # 비즈니스 로직
│   │   │   └── providers/   # AI 제공자들
│   │   ├── models/          # Pydantic 모델
│   │   └── websocket/       # WebSocket 관리
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/      # React 컴포넌트
│   │   ├── hooks/           # Custom hooks
│   │   └── services/        # API 서비스
│   └── package.json
│
└── README.md
```

## 개발 로드맵

### Phase 1 (현재) - MVP
- [x] FastAPI 백엔드
- [x] OpenAI 스트리밍 응답
- [x] 기본 채팅 UI
- [x] WebSocket 실시간 통신

### Phase 2 - 멀티 에이전트
- [ ] Claude, Gemini, Grok 지원
- [ ] 마스터 AI 로직
- [ ] 에이전트 간 대화
- [ ] 속도 조절

### Phase 3 - 사용자 경험
- [ ] 파일 첨부
- [ ] 사용자 대화 참여
- [ ] UI 개선

### Phase 4 - 배포
- [ ] PWA 설정
- [ ] 클라우드 배포
