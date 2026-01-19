# -*- coding: utf-8 -*-
"""
AP-세금계산서 매칭/업데이트 자동화 (하위 호환용 래퍼)

이 파일은 기존 호환성을 위해 유지됩니다.
새로운 모듈 구조: services/matching_engine.py
"""

from services.matching_engine import MatchingEngine
from utils.excel_utils import leave_comment

# 기존 API 호환을 위한 래퍼 함수
def run_match(ap_path=None, inv_path=None, out_path=None, *,
              on_progress=None, on_match=None, on_new=None):
    """
    기존 API 호환용 래퍼 함수

    새로운 코드에서는 MatchingEngine 클래스를 직접 사용하세요.
    """
    engine = MatchingEngine()
    return engine.run_match(
        ap_path=ap_path,
        inv_path=inv_path,
        out_path=out_path,
        on_progress=on_progress,
        on_match=on_match,
        on_new=on_new
    )


if __name__ == "__main__":
    path = run_match()
    print(f"완료: {path}")
