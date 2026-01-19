# -*- coding: utf-8 -*-
"""
엑셀 관련 유틸리티 함수
"""

from pathlib import Path
from typing import Tuple, Optional

import pandas as pd
from openpyxl.comments import Comment


def default_file(filename: str, base_dir: Optional[Path] = None) -> str:
    """
    기본 디렉토리에서 파일 경로 반환

    Args:
        filename: 파일명
        base_dir: 기준 디렉토리 (None이면 현재 모듈 위치 기준)

    Returns:
        파일 전체 경로 (존재하지 않으면 빈 문자열)
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent

    p = base_dir / filename
    return str(p.resolve()) if p.exists() else ""


def find_file_by_pattern(pattern: str, base_dir: Optional[Path] = None) -> str:
    """
    글로브 패턴으로 파일 찾기

    Args:
        pattern: 글로브 패턴 (예: "AP List_RDXL*.xlsx")
        base_dir: 기준 디렉토리

    Returns:
        첫 번째 매칭 파일 경로 (없으면 빈 문자열)
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent

    match = next(base_dir.glob(pattern), None)
    return str(match) if match else ""


def leave_comment(ws, cell_ref: str, text: str) -> None:
    """
    엑셀 셀에 주석 추가 (기존 주석이 있으면 추가)

    Args:
        ws: openpyxl 워크시트
        cell_ref: 셀 참조 (예: "A1")
        text: 추가할 주석 텍스트
    """
    cell = ws[cell_ref]
    if cell.comment:
        cell.comment = Comment(cell.comment.text + "\n" + text, "AI")
    else:
        cell.comment = Comment(text, "AI")


def lookup_bank_account(
    requester: str,
    accounts_df: pd.DataFrame
) -> Tuple[str, str]:
    """
    계좌정보 시트에서 기안자명 포함 행의 (은행, 계좌번호) 추출

    Args:
        requester: 기안자명
        accounts_df: 계좌정보 DataFrame

    Returns:
        (은행, 계좌번호) 튜플 - 없으면 빈 문자열
    """
    if accounts_df is None or accounts_df.empty or not requester:
        return "", ""

    mask = accounts_df.iloc[:, 0].fillna("").astype(str).str.contains(requester)
    if not mask.any():
        return "", ""

    row = accounts_df[mask].iloc[0]
    return str(row.iloc[1]).strip(), str(row.iloc[2]).strip()


def lookup_bank_by_supplier(
    supplier: str,
    accounts_df: pd.DataFrame
) -> Tuple[str, str]:
    """
    계좌정보 시트에서 업체명으로 (은행, 계좌번호) 조회

    Args:
        supplier: 업체명
        accounts_df: 계좌정보 DataFrame (업체명 컬럼 필요)

    Returns:
        (은행, 계좌번호) 튜플 - 없으면 "확인 필요"
    """
    if accounts_df is None or accounts_df.empty:
        return "확인 필요", "확인 필요"

    hit = accounts_df[accounts_df["업체명"].str.strip() == supplier.strip()]
    if not hit.empty:
        return hit.iloc[0]["은행"], str(hit.iloc[0]["계좌번호"])

    return "확인 필요", "확인 필요"


def load_accounts_sheet(file_path: str, sheet_name: str = "계좌정보") -> pd.DataFrame:
    """
    계좌정보 시트 로드 (없으면 빈 DataFrame 반환)

    Args:
        file_path: 엑셀 파일 경로
        sheet_name: 시트 이름

    Returns:
        계좌정보 DataFrame
    """
    try:
        return pd.read_excel(file_path, sheet_name=sheet_name)
    except ValueError:
        return pd.DataFrame()
