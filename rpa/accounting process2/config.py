"""
회계처리 분류 시스템 - 설정 및 상수
=============================================
이 파일은 앱의 기본 설정값을 정의합니다.
회계담당자도 쉽게 수정할 수 있도록 한글 주석이 포함되어 있습니다.
"""

import os

# 스크립트 경로
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ==========================================
# 디자인 시스템 (색상, 폰트)
# ==========================================
# 메인 색상
BG_COLOR = "#18181C"           # 앱 배경색 (다크)
SIDEBAR_COLOR = "#25262B"      # 사이드바 배경
ACCENT_COLOR = "#3A76F0"       # 강조 색상 (파랑)
SUCCESS_COLOR = "#50C878"      # 성공 (녹색)
WARNING_COLOR = "#FFB347"      # 경고 (주황)
ERROR_COLOR = "#FF6B6B"        # 오류 (빨강)

# 폰트
FONT_FAMILY = "Malgun Gothic"  # 기본 폰트 (한글 지원)

# ==========================================
# AI 모델 설정
# ==========================================
# 사용 가능한 AI 모델 목록
# - provider: 서비스 제공자 (openai 또는 gemini)
# - model: API에서 사용하는 모델 ID
# - description: 사용자에게 표시할 설명

AI_MODELS = {
    "GPT-5.2 (고성능)": {
        "provider": "openai",
        "model": "gpt-5.2",
        "description": "OpenAI 최신 플래그십 모델"
    },
    "GPT-5-mini (빠름)": {
        "provider": "openai",
        "model": "gpt-5-mini",
        "description": "빠른 응답, 비용 효율적"
    },
    "Gemini 3 Pro (고성능)": {
        "provider": "gemini",
        "model": "gemini-3-pro-preview",
        "description": "Google 최신 추론 모델"
    },
    "Gemini 3 Flash (빠름)": {
        "provider": "gemini",
        "model": "gemini-3-flash-preview",
        "description": "Pro급 성능, 빠른 속도"
    }
}

# 기본 사용 모델
DEFAULT_MODEL = "Gemini 3 Flash (빠름)"

# ==========================================
# 파일 지원
# ==========================================
# 지원하는 파일 형식
SUPPORTED_FILE_TYPES = {
    "pdf": "PDF 문서",
    "png": "이미지",
    "jpg": "이미지",
    "jpeg": "이미지",
    "xlsx": "Excel",
    "xls": "Excel",
    "csv": "CSV",
    "docx": "Word"
}

# ==========================================
# 분류 상태
# ==========================================
class ClassificationStatus:
    """분류 상태 코드"""
    PENDING = "미분류"           # 아직 분류되지 않음
    EXISTING = "기존분류"        # 파일에 이미 분류가 있음
    AI_CLASSIFIED = "AI분류"     # AI가 분류함
    VERIFIED = "검증완료"        # 사용자가 검증/확정함
    NEEDS_REVIEW = "검토필요"    # 추가 검토 필요

# ==========================================
# 실무지침 파일 경로
# ==========================================
GUIDELINES_JSON_PATH = os.path.join(SCRIPT_DIR, "accounting_guidelines.json")
GUIDELINES_YAML_PATH = os.path.join(SCRIPT_DIR, "accounting_guidelines.yaml")

# 버전 관리 설정
GUIDELINES_VERSIONS_DIR = os.path.join(SCRIPT_DIR, "guidelines_versions")
GUIDELINES_STATE_FILE = os.path.join(SCRIPT_DIR, ".guidelines_state.json")
MAX_VERSIONS_TO_KEEP = 30  # 최대 보관할 버전 수

# AI에게 전달할 최대 학습 케이스 수 (토큰 절약)
MAX_LEARNED_CASES_FOR_AI = 20

# ==========================================
# 키보드 단축키
# ==========================================
KEYBOARD_SHORTCUTS = {
    "next_row": "<Down>",           # 다음 행
    "prev_row": "<Up>",             # 이전 행
    "analyze": "<Control-Return>",  # AI 분석 시작
    "verify": "<Control-v>",        # 분류 확정
    "manual": "<Control-m>",        # 직접 입력
    "export": "<Control-s>",        # 내보내기
    "filter_pending": "<Control-1>", # 미분류 필터
    "filter_all": "<Control-0>",    # 전체 보기
}
