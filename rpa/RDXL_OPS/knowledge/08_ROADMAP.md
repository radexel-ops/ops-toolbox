# 08. Roadmap - VibeOps

> **문서 목적**: 프로젝트 로드맵과 진행 상황을 추적합니다.
> **상태**: LIVING DOCUMENT - 진행에 따라 업데이트

---

## 0. 현재 상태 요약 (2026-02-10)

### 완료된 작업

| 항목 | 상태 | 설명 |
|------|------|------|
| 멀티테넌트 아키텍처 | ✅ 완료 | 5개 팀 격리 구조 |
| 인증/권한 시스템 | ✅ 완료 | JWT 기반, RBAC |
| 지식 상속 시스템 | ✅ 완료 | CLAUDE.md + TEAM_CLAUDE.md 병합 |
| 프론트엔드 기본 UI | ✅ 완료 | 로그인, 대시보드, 채팅 |
| API 라우터 | ✅ 완료 | auth, teams, knowledge, bridge, agents, schedules |
| 팀 디렉토리 구조 | ✅ 완료 | teams/{slug}/ 5개 팀 |
| **코드 리팩토링** | ✅ 완료 | 보안, SVG 아이콘, Toast, a11y, XSS 방지 |
| **Agent System** | ✅ 완료 | Registry, BaseAgent, PM/News/System Agent |
| **Scheduler System** | ✅ 완료 | APScheduler, Cron/Interval/Date 지원 |
| **테스트 인프라** | ✅ 완료 | pytest, conftest, unit tests |

### 미완료 작업 (우선순위순)

| 항목 | 상태 | 우선순위 | 설명 |
|------|------|----------|------|
| 배포 스크립트 | ✅ 완료 | **높음** | deploy.sh, systemd 서비스, nginx |
| Bridge 실제 연동 | ✅ 완료 | **높음** | Claude Code CLI 스트리밍 |
| 더존 에이전트 | ✅ 완료 | **높음** | 휴가/근태 자동화 이관 |
| 에이전트 관리 UI | ✅ 완료 | 중간 | 시작/중지/로그 UI |
| DigitalOcean 배포 | ⬜ 대기 | 높음 | 실제 서버 배포 (사용자 작업) |

---

## 1. 전체 로드맵

```
Timeline (Updated: 2026-02-10)
────────────────────────────────────────────────────────────────────────
      Phase 1        Phase 2         Phase 3          Phase 4
    멀티테넌트      배포 준비 &     에이전트        사내 오픈
    + 리팩토링     AI 연동          완성
    [완료]         [완료]           [완료]          [진행 대기]
────────────────────────────────────────────────────────────────────────
```

---

## 2. Phase 1: 멀티테넌트 아키텍처 + 리팩토링 ✅ 완료

### 2.1 멀티테넌트 (완료)

| # | 태스크 | 상태 |
|---|--------|------|
| 1.1 | Database & Models | ✅ |
| 1.2 | Auth & Permission (JWT, RBAC) | ✅ |
| 1.3 | Team Structure (5개 팀) | ✅ |
| 1.4 | Knowledge Service | ✅ |
| 1.5 | Bridge Integration (구조) | ✅ |
| 1.6 | Frontend (로그인, 대시보드) | ✅ |

### 2.2 코드 리팩토링 (완료)

| # | 태스크 | 상태 | 파일 |
|---|--------|------|------|
| R.0 | SECRET_KEY 보안 강화 | ✅ | config.py |
| R.1 | SVG 아이콘 시스템 | ✅ | icons.js |
| R.2 | Toast 알림 시스템 | ✅ | toast.js |
| R.3 | 인라인 스타일 추출 | ✅ | components.css |
| R.4 | Rate Limiting | ✅ | main.py, auth.py |
| R.5 | XSS 방지 | ✅ | admin.js |
| R.6 | 접근성(a11y) | ✅ | index.html, main.js |
| R.7 | Agent System | ✅ | agents/, routers/agents.py |
| R.8 | Scheduler System | ✅ | scheduler_service.py, schedules.py |
| R.9 | Test Infrastructure | ✅ | tests/ |

---

## 3. Phase 2: 배포 준비 & AI 연동 ✅ 완료

### 3.1 Step 1: 배포 스크립트 생성 (Claude 작업) ✅

| # | 태스크 | 상태 | 파일 |
|---|--------|------|------|
| 2.1.1 | 배포 자동화 스크립트 | ✅ 완료 | scripts/deploy.sh |
| 2.1.2 | Systemd API 서비스 | ✅ 완료 | systemd/vibeops-api.service |
| 2.1.3 | Systemd Tmux 서비스 | ✅ 완료 | systemd/vibeops-tmux.service |
| 2.1.4 | Nginx 설정 예시 | ✅ 완료 | nginx/vibeops.conf |
| 2.1.5 | .env.example 업데이트 | ✅ 완료 | .env.example |

### 3.2 Step 2: Bridge 실제 연동 (Claude 작업) ✅

| # | 태스크 | 상태 | 파일 |
|---|--------|------|------|
| 2.2.1 | PTY 기반 터미널 연결 | ✅ 완료 | bridge/bridge_server.py |
| 2.2.2 | Claude Code 스트리밍 | ✅ 완료 | claude_service.py |
| 2.2.3 | WebSocket 스트리밍 전송 | ✅ 완료 | routers/bridge.py |
| 2.2.4 | 프론트엔드 스트리밍 수신 | ✅ 완료 | bridge-client.js |

### 3.3 Step 3: 인프라 준비 (사용자 작업)

| # | 태스크 | 상태 | 비고 |
|---|--------|------|------|
| 2.3.1 | DigitalOcean 계정 생성 | ⬜ 대기 | https://www.digitalocean.com |
| 2.3.2 | SSH 키 생성 및 등록 | ⬜ 대기 | `ssh-keygen -t ed25519` |
| 2.3.3 | Droplet 생성 | ⬜ 대기 | Ubuntu 24.04, 8GB RAM |
| 2.3.4 | Claude Code CLI 설치 | ⬜ 대기 | 정액제 로그인 필요 |

---

## 4. Phase 3: 에이전트 완성 ✅ 완료

| # | 태스크 | 상태 | 비고 |
|---|--------|------|------|
| 3.1 | 더존 에이전트 이관 | ✅ 완료 | VacationAgent, WehagoService |
| 3.2 | 뉴스 에이전트 완성 | ✅ 완료 | NewsAgent 구현체 존재 |
| 3.3 | 에이전트 관리 UI | ✅ 완료 | admin.html 에이전트 탭 |
| 3.4 | 스케줄 관리 UI | ✅ 완료 | admin.html 스케줄 탭 |

---

## 5. Phase 4: 사내 오픈

| # | 태스크 | 상태 |
|---|--------|------|
| 4.1 | 사용자 관리 UI | ⬜ 대기 |
| 4.2 | Super Admin 팀 선택기 | ⬜ 대기 |
| 4.3 | 대시보드 고도화 | ⬜ 대기 |
| 4.4 | 사용자 가이드 | ⬜ 대기 |
| 4.5 | 베타 테스트 | ⬜ 대기 |

---

## 6. 예상 비용

| 항목 | 월 비용 | 비고 |
|------|--------|------|
| DigitalOcean Droplet (8GB) | $48 | 고정 |
| Claude Code (정액제) | $20 | Max plan |
| Google AI API | 무료~$10 | 사용량 기반 |
| **합계** | **~$70~80** | |

---

## 7. 파일 구조 (현재)

```
RDXL_OPS/
├── agents/
│   ├── base/agent_base.py      ✅ 완료
│   ├── registry.py             ✅ 완료
│   ├── implementations/
│   │   ├── pm_agent.py         ✅ 완료
│   │   ├── news_agent.py       ✅ 완료
│   │   └── system_agent.py     ✅ 완료
│   └── douzone/
│       ├── __init__.py         ✅ 완료
│       ├── vacation_agent.py   ✅ 완료
│       └── wehago_service.py   ✅ 완료
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   │   ├── agents.py       ✅ 완료
│   │   │   ├── schedules.py    ✅ 완료
│   │   │   └── bridge.py       ✅ 완료 (스트리밍 지원)
│   │   └── services/
│   │       ├── scheduler_service.py  ✅ 완료
│   │       └── claude_service.py     ✅ 완료 (스트리밍 지원)
├── bridge/
│   ├── team_context.py         ✅ 완료
│   ├── message_types.py        ✅ 완료
│   └── bridge_server.py        ✅ 완료 (PTY 연결)
├── frontend/
│   ├── js/
│   │   ├── admin.js            ✅ 완료 (에이전트/스케줄 UI)
│   │   └── bridge-client.js    ✅ 완료 (스트리밍 지원)
│   └── css/
│       └── admin.css           ✅ 완료 (에이전트/스케줄 스타일)
├── scripts/
│   └── deploy.sh               ✅ 완료
├── systemd/
│   ├── vibeops-api.service     ✅ 완료
│   └── vibeops-tmux.service    ✅ 완료
├── nginx/
│   └── vibeops.conf            ✅ 완료
└── tests/
    ├── conftest.py             ✅ 완료
    └── unit/                   ✅ 완료
```

---

## 8. 변경 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2026-02-10 | 초기 로드맵 작성 |
| 2026-02-10 | Phase 1 완료 |
| 2026-02-10 | 리팩토링 완료 (R.0~R.9) |
| 2026-02-10 | Phase 2 상세 계획 추가 |
| 2026-02-10 | Phase 2.1 완료 (배포 스크립트, systemd, nginx) |
| 2026-02-10 | Phase 2.2 완료 (Bridge 스트리밍 연동) |
| 2026-02-10 | Phase 3.1 완료 (더존 에이전트 이관) |
| 2026-02-10 | Phase 3.2~3.4 완료 (에이전트/스케줄 관리 UI) |

---

*Last Updated: 2026-02-10*
