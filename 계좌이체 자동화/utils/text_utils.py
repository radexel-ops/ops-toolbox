# -*- coding: utf-8 -*-
"""
텍스트 파싱 관련 유틸리티 함수
"""

import re
from typing import Tuple

import pandas as pd

from config import (
    PRODUCT_MAPPINGS,
    TRAVEL_TITLE_KEYWORDS,
    TRAVEL_BODY_KEYWORDS,
    TRAVEL_BODY_THRESHOLD
)


def safe_str(x) -> str:
    """NaN이나 None을 빈 문자열로 안전하게 변환"""
    return "" if pd.isna(x) else str(x).strip()


def first_name(s: str) -> str:
    """문자열에서 첫 번째 단어(이름) 추출"""
    return str(s).split()[0] if s else ""


def safe_payee(info_payee: str, requester: str) -> str:
    """AI가 빈 문자열을 줄 때 요청자 이름으로 보정"""
    p = (info_payee or "").strip()
    return p if p else requester


def detect_product(txt: str) -> str:
    """
    텍스트에서 제품명 감지
    반환값: saber, blade, space, pilot 중 하나 또는 빈 문자열
    """
    t = txt.lower()

    # 우선순위대로 검사
    for product, keywords in PRODUCT_MAPPINGS.items():
        pattern = "|".join(keywords)
        if re.search(pattern, t, re.I):
            return product

    return ""


def parse_bank_info(txt: str) -> Tuple[str, str, str]:
    """
    본문에서 '입금 계좌' 라인을 찾아
    은행명 / 계좌번호 / 예금주 형태(슬래시로 구분)를 파싱한다.

    Returns:
        (은행, 계좌번호, 예금주) - 없으면 빈 문자열
    """
    bank = account = holder = ""
    m = re.search(r"입금\s*계좌[^\n]*[:\-]\s*([^\n]+)", txt, re.I)
    if m:
        line = m.group(1)
        # 슬래시 · 풀각 슬래시 모두 분리
        parts = [p.strip() for p in re.split(r"[／/]", line)]
        if parts:
            bank = parts[0]
        if len(parts) >= 2:
            account = parts[1]
        if len(parts) >= 3:
            # '예금주:' 가 붙어 있으면 제거
            h = re.sub(r"^\s*예금주\s*[:\-]?\s*", "", parts[2], flags=re.I)
            holder = h.strip()
    return bank, account, holder


def is_travel_reimbursement(title: str, body: str) -> bool:
    """
    제목·본문 키워드로 여비정산 서식 여부 판단

    Returns:
        True if 여비정산 문서로 판단됨
    """
    # 제목 키워드 검사
    if any(k in title for k in TRAVEL_TITLE_KEYWORDS):
        return True

    # 본문 키워드 검사 (임계값 이상이면 여비정산)
    keyword_count = sum(k in body for k in TRAVEL_BODY_KEYWORDS)
    return keyword_count >= TRAVEL_BODY_THRESHOLD


def normalize_header(s: str) -> str:
    """헤더 문자열 정규화 (공백/개행 제거)"""
    return str(s or "").strip().replace(" ", "")
