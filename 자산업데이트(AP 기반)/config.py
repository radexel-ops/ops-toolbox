# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json

# ───────────────────────── OpenAI 기본 설정 ─────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-5-mini").strip()

# ───────────────────────── Google OAuth / Sheets API ─────────────────────────
# gsheets_client.py에서 import 합니다.
# 최소 권한: 스프레드시트 읽기/쓰기
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def _from_cfg(key: str, default: str = "") -> str:
    """config.json에서 값을 읽는 폴백 헬퍼"""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return (json.load(f).get(key, default) or "").strip()
    except Exception:
        return (default or "").strip()

# ① 환경변수 우선 → ② config.json 값 폴백
GOOGLE_CLIENT_ID = (os.getenv("GOOGLE_CLIENT_ID", "").strip()
                    or _from_cfg("GOOGLE_CLIENT_ID", ""))
GOOGLE_CLIENT_SECRET = (os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
                        or _from_cfg("GOOGLE_CLIENT_SECRET", ""))
# (선택) client_secret.json 파일 경로를 직접 지정하려면 사용
GOOGLE_CLIENT_SECRETS_FILE = (os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "").strip()
                              or _from_cfg("GOOGLE_CLIENT_SECRETS_FILE", ""))

# ───────────────────────── 앱 기본 설정(DEFAULT_CONFIG) ─────────────────────────
# app_main.py에서 config.json을 읽고, 이 DEFAULT_CONFIG와 병합하여 self.cfg를 만듭니다.
DEFAULT_CONFIG = {
    # Google Sheets (반드시 config.json에서 실제 ID/시트를 덮어써 주세요)
    "AP_SPREADSHEET_ID": "",
    "AP_SHEET_NAME": "AP 리스트",
    "ASSETS_SPREADSHEET_ID": "",
    "ASSETS_SHEET_NAME": "자산현황",

    # 자산현황 2행을 템플릿 행으로 가정(수식/서식 복사 기준)
    "ASSETS_TEMPLATE_ROW_INDEX_1_BASED": 2,

    # 필수/제외 헤더
    "REQUIRED_HEADERS": ["관리번호 (필수)", "카테고리 (필수)", "모델 (필수)", "자산상태 (필수)"],
    "EXCLUDED_HEADERS": [
        "관리번호 검증","관리번호 앞자리","회계처리","자산코드","장부명","신규취득","잔존가치",
        "OS","CPU","RAM","HDD/SSD","그래픽","화면크기","관리팀","메모 (255자 제한)","사용자 이메일"
    ],

    # OpenAI
    "OPENAI_MODEL": OPENAI_MODEL,
    "CONFIDENCE_THRESHOLD": 0.90,
    "AI_TIMEOUT_SEC": 30,
    "AI_CONFIDENCE_IF_MISSING": 0.95,
    "AI_DEBUG_LOG": True,
    "AI_ALLOW_OVERWRITE": False,
    "ASSETS_CONTEXT_MAX_ROWS": 120,
    "CATEGORY_FUZZY_MIN_SCORE": 0.65,
    "ALLOW_CATEGORY_FALLBACK": False,
    "CATEGORY_FALLBACK_VALUE": "미분류",

    # 관리번호 프리픽스 규칙(카테고리별). 일치 항목이 없으면 'AS' 사용.
    "PREFIX_RULES": {
        "IT-PC": "IT", "IT-랩탑": "IT", "IT-모니터": "IT", "IT-네트워크 장비": "IT", "IT-서버": "IT",
        "가구-책상": "FU", "가구-의자": "FU", "가구-회의용 테이블": "FU",
        "장치-제조 설비": "EQ", "장치-R&D용 장비": "EQ",
        "제품-SABER 제품": "PR", "제품-BLADE 제품": "PR", "제품-VISION 제품": "PR", "제품-SPACER 제품": "PR",
        "SW-영구 라이선스": "SW", "SW-구독 라이선스": "SW",
        "개발비-SABER 인허가": "RD", "개발비-BLADE 인허가": "RD", "개발비-VISION 인허가": "RD", "개발비-SPACER 인허가": "RD",
        "지재권-특허": "IP", "지재권-기타": "IP",
        "예치금-사옥·설비 임대차 보증금": "DE",
        "투자-타사 지분투자": "IV",
        "리스-IFRS16 적용: 차량 리스": "LS",
        "부동산-본사·공장·연구소 건물(소유)": "RE",
        "차량-회사 업무용 차량": "VE",
    },

    # (선택) config.json에 OAuth 자격값을 둘 때 사용
    "GOOGLE_CLIENT_ID": "",
    "GOOGLE_CLIENT_SECRET": "",
    "GOOGLE_CLIENT_SECRETS_FILE": "",
}

# ───────────────────────── AP 시트 헤더 별칭 ─────────────────────────
AP_COL_ALIASES = {
    "문서번호": ["문서번호", "문서 번호", "문서 No", "문서No", "Doc No", "문서 번호 "]
}

AP_SIMPLY_HEADERS = [
    "심플리 등록", "심플리등록", "등록", "SIMPLY", "Simply", "O표기", "O/X", "심플리 표기"
]

STOPWORDS_IN_TITLE = [
    "지출품의", "품의서", "의", "건", "세금계산서", "전자세금계산서", "계약금", "중도금", "잔금", "완료금",
    "부가세", "VAT", "영수증", "계정", "비고", "구매", "결재", "품목", "내역"
]
