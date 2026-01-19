# -*- coding: utf-8 -*-
"""
날짜 관련 유틸리티 함수
"""

import re
import calendar
from datetime import datetime, date
from typing import Optional, Union

import pandas as pd
import openai

from prompts import SECOND_THURSDAY_PROMPT_TEMPLATE


def extract_date(s: Union[str, datetime, date, pd.Timestamp, None]) -> str:
    """
    입력이 다음 중 어떤 형태든 YYYYMMDD(8자리) 문자열로 반환
      1) '2025.06.26' '2025-06-26' '2025/06/26'
      2) '20250626'
      3) datetime, pd.Timestamp 객체
    매칭 실패 시 빈 문자열 반환
    """
    if s is None:
        return ""

    # datetime, Timestamp 직접 처리
    if isinstance(s, (datetime, date, pd.Timestamp)):
        return s.strftime("%Y%m%d")

    txt = str(s)

    # 구분자 포함 형태
    m = re.search(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", txt)
    if m:
        y, mth, d = m.groups()
        return f"{y}{mth.zfill(2)}{d.zfill(2)}"

    # 구분자 없는 8자리
    m = re.search(r"\b(\d{8})\b", txt)
    if m:
        return m.group(1)

    return ""


def next_second_friday(from_day: Optional[date] = None) -> str:
    """
    기준 날짜 이후 '다가오는 가장 가까운 매월 2번째 목요일'을
    OpenAI-API에게 물어보고 YYYYMMDD 형태로 반환한다.
    - API 호출 실패 시 로컬 계산으로 폴백
    """
    d = from_day or date.today()

    prompt = SECOND_THURSDAY_PROMPT_TEMPLATE.format(today=d.strftime('%Y-%m-%d'))

    try:
        rsp = openai.chat.completions.create(
            model="o4-mini",
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            max_tokens=10
        )
        answer = rsp.choices[0].message.content.strip()
        m = re.search(r"\d{4}[./-]\d{2}[./-]\d{2}", answer)
        if m:
            # API 응답 내 구분자 모두 제거
            return m.group().replace("-", "").replace("/", "")
    except Exception:
        # API 오류나 날짜 파싱 실패 시 로컬 계산 폴백
        pass

    # 폴백: 파이썬 자체 계산
    return _calculate_second_friday_local(d)


def _calculate_second_friday_local(from_date: date) -> str:
    """로컬에서 두 번째 금요일 계산 (폴백용)"""
    y, m = from_date.year, from_date.month
    while True:
        _, days = calendar.monthrange(y, m)
        fridays = [day for day in range(1, days + 1)
                   if calendar.weekday(y, m, day) == 4]  # 4 = Friday
        second = date(y, m, fridays[1])
        if second >= from_date:
            return second.strftime("%Y%m%d")
        m += 1
        if m == 13:
            y, m = y + 1, 1


def format_raw_date(raw_date: str) -> str:
    """
    웹에서 수집한 날짜 문자열을 YYYYMMDD 형식으로 변환
    예: "2025.6.2" -> "20250602", "2025.06.26" -> "20250626"
    """
    m = re.match(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})", raw_date)
    if m:
        y, mo, da = m.groups()
        return f"{y}{mo.zfill(2)}{da.zfill(2)}"
    # 매끄럽지 않은 포맷인 경우, 구분자만 제거
    return raw_date.replace(".", "").replace("-", "").replace("/", "")
