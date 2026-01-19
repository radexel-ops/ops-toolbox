# RDXL RPA Toolbox

라덱셀 업무 자동화 스크립트 모음

## 빠른 시작 (팀원용)

### 1. 저장소 클론
```bash
git clone https://github.com/radexel-ops/ops-toolbox.git
cd ops-toolbox
```

### 2. 개인 설정 파일 생성
```bash
# .env.local.example 파일을 복사하여 .env.local 생성
cp .env.local.example .env.local
```

### 3. 개인 정보 입력
`.env.local` 파일을 열어서 본인의 WEHAGO 계정 정보 입력:
```
WEHAGO_ID=본인_위하고_아이디
WEHAGO_PW=본인_위하고_비밀번호
```

### 4. 의존성 설치
```bash
pip install -r requirements.txt
```

---

## 환경변수 구조

| 파일 | 용도 | Git 포함 |
|------|------|----------|
| `.env.shared` | 팀 공용 API 키 (Slack, Google, OpenAI) | O |
| `.env.local` | 개인 로그인 정보 (WEHAGO 등) | X |
| `.env.local.example` | 개인 설정 템플릿 | O |

---

## 프로젝트 구조

```
ops-toolbox/
├── index.html, expense.html    # 웹 도구 (GitHub Pages)
├── rdxl_automation.py          # 메인 자동화 스크립트
├── .env.shared                 # 팀 공용 설정
├── .env.local                  # 개인 설정 (각자 생성)
│
└── rpa/                        # RPA 프로젝트들
    ├── NEWS_SCRAPPING/         # 뉴스 스크래핑
    ├── 직원 휴가일정 업데이트/   # WEHAGO → Google Calendar
    ├── accounting process/     # 회계 자동화
    └── ...
```

---

## 주요 기능

- **뉴스 스크래핑**: 자동으로 뉴스 수집 후 Slack 전송
- **휴가 일정 동기화**: WEHAGO 휴가 → Google Calendar 자동 동기화
- **근태 알림**: 매일 아침 부재자 Slack 알림
- **회계 처리**: 결재 문서 자동 분류

---

## 문의

내부 Slack #automation 채널
