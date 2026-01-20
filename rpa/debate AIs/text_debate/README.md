# AI Debate System

Gemini와 GPT가 사용자의 질문에 대해 토론하여 **상호 합의**를 도출하는 터미널 기반 시스템입니다.

## 주요 기능

- **AI 토론**: Gemini와 GPT가 번갈아가며 의견을 교환하고 비판적으로 검토
- **상호 합의 도출**: 양쪽 AI 모두 `[AGREED]`를 출력해야 토론 종료
- **다중 파일 첨부**: 이미지, PDF, Excel, Word, 텍스트, 비디오 등 다양한 파일 형식 지원
- **컨텍스트 상속**: 추가 질문 시 이전 토론 내용이 자동으로 유지됨
- **HTML 히스토리**: 채팅 형식의 가독성 높은 HTML 파일로 토론 기록 저장
- **유연한 설정**: config.yaml을 통해 모델, 프롬프트, 최대 턴 수 등 커스터마이징

## 설치

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. API 키 설정

`.env` 파일을 열어 API 키를 입력하세요:

```ini
GOOGLE_API_KEY=your_actual_google_api_key
OPENAI_API_KEY=your_actual_openai_api_key
```

API 키 발급:
- Google Gemini: https://aistudio.google.com/app/apikey
- OpenAI: https://platform.openai.com/api-keys

## 사용법

### 기본 실행

```bash
python main.py
```

### 실행 흐름

1. **모델 선택**: Gemini 모델과 GPT 모델 선택
2. **질문 입력**: 토론할 주제/질문 입력
3. **파일 첨부** (선택): 분석할 파일 경로 입력 (쉼표로 구분)
4. **토론 진행**: AI들이 자동으로 토론 진행
5. **합의 도출**: 양측 모두 합의하면 종료
6. **추가 질문** (선택): 결과를 바탕으로 후속 질문 가능

### 예시

```
질문을 입력하세요: 이 재무제표를 분석하고 내년도 마케팅 전략을 제안해줘
첨부 파일 경로: financial_report.xlsx, company_logo.png

[Gemini가 첫 의견 제시]
[GPT가 비판 및 보완]
[Gemini가 수정안 제시]
[GPT가 동의 -> [AGREED]]
[Gemini가 최종 합의 -> [AGREED]]

상호 합의 도출 완료!
```

## 파일 구조

```
ai_debate/
├── main.py           # 메인 실행 파일
├── utils.py          # 파일 처리 및 HTML 로깅 유틸리티
├── config.yaml       # 설정 파일 (커스터마이징 가능)
├── .env              # API 키 (보안 - git에 커밋하지 마세요)
├── .env.example      # API 키 템플릿
├── requirements.txt  # 의존성 목록
├── README.md         # 사용 설명서
└── history/          # 토론 기록 HTML 파일 저장 폴더
```

## 설정 (config.yaml)

### 주요 설정 항목

```yaml
system:
  max_turns: 50          # 최대 토론 턴 수 (0 = 무한)
  consensus_token: "[AGREED]"  # 합의 토큰
  history_dir: "./history"     # 히스토리 저장 경로
  output_mode: "verbose"       # verbose(상세) / minimal(간략)

models:
  google:
    "Gemini 3 Flash (Preview)": "gemini-3-flash-preview"
    "Gemini 1.5 Pro": "gemini-1.5-pro"  # 테스트용
  openai:
    "GPT-5 Mini": "gpt-5-mini"
    "GPT-4o": "gpt-4o"  # 테스트용
```

### 프롬프트 커스터마이징

`config.yaml`의 `prompts` 섹션에서 AI의 행동 방식을 수정할 수 있습니다:

```yaml
prompts:
  system_instruction: |
    당신은 전문적이고 논리적인 AI 토론자입니다.
    ...
```

## 지원 파일 형식

| 카테고리 | 확장자 |
|---------|--------|
| 텍스트 | .txt, .md, .py, .js, .ts, .java, .c, .cpp, .json, .yaml, .csv, .html, .xml |
| 이미지 | .jpg, .jpeg, .png, .gif, .webp, .bmp |
| 문서 | .pdf, .docx, .xlsx, .pptx |
| 미디어 | .mp4, .mp3, .wav, .avi, .mov, .webm |

**참고**: 미디어 파일은 Gemini에서만 직접 처리 가능합니다. GPT는 텍스트/이미지만 직접 지원합니다.

## 토론 종료 조건

1. **상호 합의**: 양쪽 AI 모두 `[AGREED]`를 출력
2. **최대 턴 도달**: `max_turns` 설정값에 도달 (강제 종료)
3. **사용자 종료**: `exit` 또는 `quit` 입력

## HTML 히스토리

토론이 끝나면 `./history/` 폴더에 HTML 파일이 생성됩니다:

- 파일명: `debate_YYYYMMDD_HHMMSS.html`
- 내용: 사용자 질문, AI 대화, 첨부파일, 합의 결과 등
- 채팅 UI 스타일로 가독성 높게 렌더링

## 모델 참고사항

현재 config.yaml에 설정된 모델 중 일부(gemini-3-*, gpt-5-*)는 미래 모델입니다.

**테스트 시** 사용 가능한 모델:
- Google: `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-2.0-flash`
- OpenAI: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`

새 모델이 출시되면 `config.yaml`의 모델 ID만 업데이트하면 됩니다.

## 문제 해결

### API 키 오류
```
GOOGLE_API_KEY가 설정되지 않았습니다.
```
-> `.env` 파일에 올바른 API 키를 입력했는지 확인

### 모델을 찾을 수 없음
```
[Gemini 오류] 모델 'gemini-3-flash-preview'을(를) 사용할 수 없습니다.
```
-> `config.yaml`에서 현재 사용 가능한 모델로 변경

### 파일 처리 오류
```
[파일 읽기 오류: ...]
```
-> 파일 경로가 정확한지, 파일이 손상되지 않았는지 확인

## 라이선스

MIT License
