# -*- coding: utf-8 -*-
"""
OpenAI API 서비스
"""

import re
import json
from typing import List, Dict, Optional

import openai

from config import DEFAULT_OPENAI_API_KEY, DEFAULT_OPENAI_MODEL, SUPPORTED_MODELS
from prompts import MULTI_TRANSFER_PROMPT, MATCH_PROMPT_TEMPLATE, NEW_ROW_PROMPT


class OpenAIService:
    """OpenAI API 래퍼 클래스"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Args:
            api_key: OpenAI API 키 (None이면 환경변수 사용)
            model: 사용할 모델명
        """
        self.api_key = api_key or DEFAULT_OPENAI_API_KEY
        self.model = model or DEFAULT_OPENAI_MODEL
        openai.api_key = self.api_key

    def set_api_key(self, api_key: str) -> None:
        """API 키 설정"""
        self.api_key = api_key
        openai.api_key = api_key

    def set_model(self, model: str) -> None:
        """모델 설정"""
        self.model = model

    def get_available_models(self) -> List[str]:
        """
        사용 가능한 모델 목록 조회

        Returns:
            모델 ID 리스트
        """
        try:
            lst = [m.id for m in openai.models.list().data]
            usable = sorted({m for m in lst
                             if re.match(r"(gpt-\d|gpt-4|gpt-3|o[0-9])", m, re.I)})
            return usable if usable else SUPPORTED_MODELS
        except Exception:
            return SUPPORTED_MODELS

    def _get_model_kwargs(self) -> dict:
        """모델별 적절한 토큰 파라미터 반환"""
        if self.model.startswith(("o3", "gpt-4o", "o4")):
            return {"max_completion_tokens": 4096}
        return {"max_tokens": 4096}

    def parse_multi_transfer(self, text: str) -> List[Dict]:
        """
        본문에서 다중 이체건 정보 파싱

        Args:
            text: 문서 본문

        Returns:
            이체건 정보 딕셔너리 리스트
        """
        try:
            rsp = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": MULTI_TRANSFER_PROMPT},
                    {"role": "user", "content": text[:12000]}
                ],
                stream=False,
                **self._get_model_kwargs()
            )
            m = re.search(r"\[.*\]", rsp.choices[0].message.content, re.S)
            return json.loads(m.group()) if m else []
        except Exception:
            # 멀티 파싱 실패 시 단일 파싱으로 폴백
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
        try:
            rsp = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": MULTI_TRANSFER_PROMPT},
                    {"role": "user", "content": text[:12000]}
                ],
                stream=False,
                **self._get_model_kwargs()
            )
            full = rsp.choices[0].message.content
            m = re.search(r"\{.*\}", full, re.S)
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
            rsp = openai.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                stream=False
            )
            # 숫자만 추출
            idx = int(re.search(r"-?\d+", rsp.choices[0].message.content).group())
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

        try:
            rsp = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": NEW_ROW_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False
            )
            data = json.loads(
                re.search(r"\{.*\}", rsp.choices[0].message.content, re.S).group()
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
