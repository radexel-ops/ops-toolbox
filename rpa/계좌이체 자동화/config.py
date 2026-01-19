# -*- coding: utf-8 -*-
"""
설정 및 상수 정의
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# ── 경로 설정 ────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"  # 문서 전체 수집 저장 경로

# ── 파일명 기본값 ────────────────────────────────────────
DEFAULT_DB_TEMP = "db_temp.xlsx"
DEFAULT_AP_LIST = "AP List_RDXL.xlsx"
DEFAULT_AP_LIST_UPDATED = "AP List_RDXL_updated.xlsx"
DEFAULT_AP_LIST_MERGED = "AP List_RDXL_merged.xlsx"
DEFAULT_TAX_INVOICE_PATTERN = "매입전자세금계산서목록*.xls"

# ── Wehago 설정 ──────────────────────────────────────────
WEHAGO_LOGIN_URL = "https://www.wehago.com/#/login"
WEHAGO_SERVICE_URL = "https://www.wehago.com/#/eapprovals/menu/servicemanagement"
WEHAGO_ACCOUNT_URL = (
    "https://smarta.wehago.com/#/smarta/account/SAAC0107?"
    "sao&cno=2956135&cd_com=biz202312040013897&gisu=8&yminsa=2025&"
    "searchData=2025010120251231&color=#F09A1E&"
    "companyName=%EC%A3%BC%EC%8B%9D%ED%9A%8C%EC%82%AC%20%EB%9D%BC%EB%8D%B1%EC%85%80&"
    "companyID=pop84268"
)

# ── Wehago CSS 셀렉터 ────────────────────────────────────
SEL_BODY_IFRAME = "iframe#wehago_dze"
SEL_TITLE = "#BODY_CLASS div.dialog_content.lg.ea_dialog tr:nth-child(1) td"
SEL_DOCNO = "#BODY_CLASS div.dialog_content.lg.ea_dialog tr:nth-child(2) td"
SEL_DATE = "#BODY_CLASS div.dialog_content.lg.ea_dialog tr:nth-child(3) td"
SEL_WRITER = "#BODY_CLASS div.dialog_content.lg.ea_dialog tr:nth-child(4) td"

# ── 첨부 파일 셀렉터 ─────────────────────────────────────
SEL_DIALOG_CONTENT = "#BODY_CLASS div.dialog_content.lg.ea_dialog"
SEL_ATTACHMENT_ZONE = "div.attached_filezone"
SEL_ATTACHMENT_SAVE_ALL_BTN = "div.attached_filezone button.LUX_basic_btn"

# ── OpenAI 설정 ──────────────────────────────────────────
DEFAULT_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_OPENAI_MODEL = "o4-mini"
SUPPORTED_MODELS = ["o3", "o4-mini"]

# ── Gemini 설정 ──────────────────────────────────────────
DEFAULT_GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "")
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"

# ── AP List 컬럼 ─────────────────────────────────────────
AP_COLUMNS = [
    "기안 날짜", "세금계산서 수령", "이체 목표", "이체 날짜", "요청자",
    "구분", "품목", "문서번호", "비고", "은행", "계좌번호", "금액", "수취인",
    "공란", "CMS코드(공란)", "받는분 통장 표시", "본인 통장표시내용", "내부 메모",
    "세금 계산서 내용"
]

# ── 구분 허용 값 ─────────────────────────────────────────
ALLOWED_CATEGORIES = [
    "기타수수료", "교육비", "부품구매", "외주용역", "R&D비품", "지재권", "개발SW",
    "착오송금환입", "복지비", "PC부속품", "사무잡비", "업무툴", "여비", "인테리어",
    "공용비품", "가구", "임대관리비", "접대비", "채용비용", "수익", "급상여", "사회보험",
    "관세", "주민세", "원천세", "부가세", "법인세", "여비정산", "관리비"
]

# ── 제품 매핑 ────────────────────────────────────────────
PRODUCT_MAPPINGS = {
    "saber": ["saber", "세이버", "magsaber", "맥세이버"],
    "blade": ["blade", "블레이드", "magblade"],
    "space": ["space", "spacer", "스페이서", "magspacer"],
    "pilot": ["pilot", "파일럿", "magpilot"]
}

# ── 여비정산 키워드 ──────────────────────────────────────
TRAVEL_TITLE_KEYWORDS = ("지출승인요청", "여비정산", "출장경비")
TRAVEL_BODY_KEYWORDS = ("이동구간", "출장목적", "유류비", "통행료", "네이버 길찾기", "톨게이트")
TRAVEL_BODY_THRESHOLD = 3  # 본문 키워드 최소 매칭 개수

# ── UI 설정 ──────────────────────────────────────────────
UI_BASE_WIDTH = 720
UI_EXPAND_DELTA = 600
COMPANY_NAME = "주식회사 라덱셀"

# ── 세금계산서 매칭 UI 컬럼 ───────────────────────────────
TAX_MATCH_COLUMNS = [
    ("inv_승인번호", 130), ("ap_세금계산서수령", 130),
    ("inv_상호", 120), ("ap_수취인", 120),
    ("inv_품목", 180), ("ap_품목", 180),
    ("inv_합계금액", 95), ("ap_금액", 95),
    ("금액차이", 80), ("이체목표", 120),
    ("내부메모", 180), ("비고", 180),
    ("ACTION", 60),
]

# ── 외부 링크 ────────────────────────────────────────────
LINKS = {
    "ap_list": "https://docs.google.com/spreadsheets/d/1vzqrQsOM45pBOBbTBQVoxDi2BuMGP2a9YUIl9PilnyM/edit?gid=1227911203#gid=1227911203",
    "hometax": "https://hometax.go.kr/websquare/websquare.html?w2xPath=/ui/pp/index_pp.xml&menuCd=index3"
}
