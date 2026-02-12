# VibeOps

**AI-First 운영 자동화 플랫폼**

경영기획팀이 직접 만들고 운영하는 업무 자동화 시스템

---

## 프로젝트 개요

VibeOps는 웹 인터페이스를 통해 Claude Code와 대화하며 실시간으로 업무 자동화 도구를 개발하고 운영할 수 있는 플랫폼입니다.

### 핵심 목표

1. **개발팀 의존 탈피**: 경영기획팀이 직접 서버/DB를 관리
2. **대화형 개발**: 웹에서 AI와 대화하며 새 기능 개발
3. **1인 1 AI 에이전트**: 전 임직원 개인화 자동화 환경 제공

---

## 시작하기

### 로컬 개발 환경

```bash
# 1. 저장소 클론
git clone <repository-url>
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

# 6. 브라우저에서 접속
# http://localhost:8000
```

---

## 프로젝트 구조

```
RDXL_OPS/
├── CLAUDE.md                 # 프로젝트 지침 (헌법)
├── README.md                 # 이 파일
├── knowledge/                # 상세 지식 문서
│   ├── 01_VISION.md
│   ├── 02_ARCHITECTURE.md
│   ├── 03_BRIDGE_SYSTEM.md
│   ├── 04_AGENTS.md
│   ├── 05_DEPLOYMENT.md
│   ├── 06_DEVELOPMENT.md
│   ├── 07_OPERATIONS.md
│   ├── 08_ROADMAP.md
│   └── 09_MODULE_REGISTRY.md
├── backend/                  # FastAPI 백엔드
│   ├── app/
│   └── requirements.txt
├── frontend/                 # 웹 대시보드
│   ├── index.html
│   ├── css/
│   └── js/
├── bridge/                   # 브릿지 시스템
├── agents/                   # 자동화 에이전트
├── .claude/                  # Claude Code 설정
├── .env.example              # 환경변수 예시
└── .gitignore
```

---

## 문서

| 문서 | 설명 |
|------|------|
| [CLAUDE.md](./CLAUDE.md) | 프로젝트 헌법, 7대 원칙 |
| [01_VISION.md](./knowledge/01_VISION.md) | 비전 및 목표 |
| [02_ARCHITECTURE.md](./knowledge/02_ARCHITECTURE.md) | 시스템 아키텍처 |
| [03_BRIDGE_SYSTEM.md](./knowledge/03_BRIDGE_SYSTEM.md) | 브릿지 시스템 설계 |
| [04_AGENTS.md](./knowledge/04_AGENTS.md) | 에이전트 개발 가이드 |
| [05_DEPLOYMENT.md](./knowledge/05_DEPLOYMENT.md) | DigitalOcean 배포 가이드 |
| [06_DEVELOPMENT.md](./knowledge/06_DEVELOPMENT.md) | 개발 컨벤션 |
| [07_OPERATIONS.md](./knowledge/07_OPERATIONS.md) | 운영/보안 |
| [08_ROADMAP.md](./knowledge/08_ROADMAP.md) | 로드맵 |
| [09_MODULE_REGISTRY.md](./knowledge/09_MODULE_REGISTRY.md) | 모듈 카탈로그 |

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | FastAPI, Python 3.11+ |
| Frontend | HTML/CSS/JS (Vanilla) |
| Database | SQLite |
| Server | DigitalOcean Droplet (Ubuntu 24.04) |
| Process | Tmux |
| Automation | Selenium, Playwright |

---

## 로드맵

- **Phase 1**: 인프라 & 기본 환경 구축
- **Phase 2**: 브릿지 시스템 개발
- **Phase 3**: 에이전트 개발 (더존, 뉴스)
- **Phase 4**: 사내 오픈

자세한 내용은 [08_ROADMAP.md](./knowledge/08_ROADMAP.md) 참조

---

## 라이선스

Private - 내부 사용 전용

---

*Created: 2026-02-10*
