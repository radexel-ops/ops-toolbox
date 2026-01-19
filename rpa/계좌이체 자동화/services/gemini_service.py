# -*- coding: utf-8 -*-
"""
Gemini API 서비스 (세금계산서 매칭용)
"""

import re
import json
from typing import List, Dict, Optional

import google.generativeai as genai

from config import DEFAULT_GEMINI_API_KEY, DEFAULT_GEMINI_MODEL
from prompts import MULTI_TRANSFER_PROMPT, MATCH_PROMPT_TEMPLATE, NEW_ROW_PROMPT


class GeminiService:
    """Gemini API 래퍼 클래스"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Args:
            api_key: Gemini API 키 (None이면 환경변수 사용)
            model: 사용할 모델명
        """
        self.api_key = api_key or DEFAULT_GEMINI_API_KEY
        self.model_name = model or DEFAULT_GEMINI_MODEL
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)

    def set_api_key(self, api_key: str) -> None:
        """API 키 설정"""
        self.api_key = api_key
        genai.configure(api_key=api_key)

    def set_model(self, model: str) -> None:
        """모델 설정"""
        self.model_name = model
        self.model = genai.GenerativeModel(model)

    def parse_multi_transfer(self, text: str) -> List[Dict]:
        """
        본문에서 다중 이체건 정보 파싱

        Args:
            text: 문서 본문

        Returns:
            이체건 정보 딕셔너리 리스트
        """
        full_prompt = f"{MULTI_TRANSFER_PROMPT}\n\n{text[:12000]}"

        try:
            response = self.model.generate_content(full_prompt)
            m = re.search(r"\[.*\]", response.text, re.S)
            return json.loads(m.group()) if m else []
        except Exception:
            result = self.parse_single_transfer(text)
            return [result] if result else []

    def parse_single_transfer(self, text: str) -> Dict:
        """
        본문에서 단일 이체건 정보 파싱

        Args:
            text: 문서 본문

        Returns:
            이체건 정보 딕셔너리
        """
        full_prompt = f"{MULTI_TRANSFER_PROMPT}\n\n{text[:12000]}"

        try:
            response = self.model.generate_content(full_prompt)
            m = re.search(r"\{.*\}", response.text, re.S)
            return json.loads(m.group()) if m else {}
        except Exception:
            return {}

    def find_matching_ap_row(
        self,
        invoice_dict: Dict,
        ap_candidates: List[Dict]
    ) -> int:
        """
        세금계산서와 매칭되는 AP 행 인덱스 찾기

        Args:
            invoice_dict: 세금계산서 정보
            ap_candidates: AP 후보 리스트

        Returns:
            매칭된 행 인덱스 (-1이면 매칭 없음)
        """
        prompt = MATCH_PROMPT_TEMPLATE.format(
            invoice_json=json.dumps(invoice_dict, ensure_ascii=False, indent=2),
            ap_rows_json=json.dumps(ap_candidates, ensure_ascii=False, indent=2)
        )

        try:
            response = self.model.generate_content(prompt)
            # 숫자만 추출
            idx = int(re.search(r"-?\d+", response.text).group())
            return idx if -1 <= idx < len(ap_candidates) else -1
        except Exception:
            return -1

    def generate_new_ap_row(self, invoice_dict: Dict) -> Dict:
        """
        신규 AP 행의 구분·은행·계좌번호·내부메모 생성

        Args:
            invoice_dict: 세금계산서 정보

        Returns:
            생성된 필드 딕셔너리
        """
        user_prompt = f"invoice = {json.dumps(invoice_dict, ensure_ascii=False)}"
        full_prompt = f"{NEW_ROW_PROMPT}\n\n{user_prompt}"

        try:
            response = self.model.generate_content(full_prompt)
            data = json.loads(
                re.search(r"\{.*\}", response.text, re.S).group()
            )
            # 필수 키 채워 넣기
            for k in ("구분", "은행", "계좌번호", "내부메모"):
                data.setdefault(k, "확인 필요")
            return data
        except Exception:
            return {
                "구분": "검토 필요",
                "은행": "확인 필요",
                "계좌번호": "확인 필요",
                "내부메모": "(구분)내역 확인"
            }
