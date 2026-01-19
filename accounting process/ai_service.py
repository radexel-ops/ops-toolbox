"""
AI 서비스 모듈
==============
OpenAI, Google Gemini API를 통한 AI 분석 기능을 제공합니다.

지원 모델:
- OpenAI: GPT-5.2, GPT-5-mini
- Google: Gemini 3 Pro, Gemini 3 Flash
"""

import os
import json
from typing import Dict, List, Optional
from dotenv import load_dotenv

from config import AI_MODELS, DEFAULT_MODEL, SCRIPT_DIR
from guidelines_manager import build_ai_prompt

# 환경변수 로드
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")
load_dotenv(ENV_PATH, override=True)

# API 클라이언트 임포트
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


class AccountingAI:
    """
    회계처리 AI 분석 클래스

    사용 예시:
        ai = AccountingAI()
        result = ai.analyze(row_data, history)
    """

    def __init__(self, model_name: str = None):
        """
        AI 초기화

        Args:
            model_name: 사용할 모델명 (config.py의 AI_MODELS 키)
        """
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.google_key = os.getenv("GOOGLE_API_KEY")

        # 모델 설정
        if model_name is None:
            model_name = DEFAULT_MODEL

        if model_name not in AI_MODELS:
            raise ValueError(f"지원하지 않는 모델: {model_name}")

        model_config = AI_MODELS[model_name]
        self.provider = model_config["provider"]
        self.model = model_config["model"]
        self.model_name = model_name

        # API 클라이언트 초기화
        self._init_client()

    def _init_client(self):
        """API 클라이언트 초기화"""
        if self.provider == "openai":
            if not self.openai_key:
                raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
            if not HAS_OPENAI:
                raise ValueError("openai 라이브러리가 설치되지 않았습니다. pip install openai")
            self.client = OpenAI(api_key=self.openai_key)

        elif self.provider == "gemini":
            if not self.google_key:
                raise ValueError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")
            if not HAS_GEMINI:
                raise ValueError("google-generativeai 라이브러리가 설치되지 않았습니다.")
            genai.configure(api_key=self.google_key)

    def analyze(self, row_data: str, history: List[Dict] = None) -> Dict:
        """
        거래 데이터 분석

        Args:
            row_data: 분석할 거래 데이터 (JSON 문자열)
            history: 이전 대화 기록

        Returns:
            Dict: AI 응답
                - status: "INCOMPLETE" | "COMPLETE" | "ERROR"
                - message: 사용자에게 보여줄 메시지
                - questions: 추가 질문 목록 (INCOMPLETE일 때)
                - final_classification: 최종 분류 (COMPLETE일 때)
                - account_code: 계정 코드 (COMPLETE일 때)
                - reasoning: 판단 근거
        """
        if history is None:
            history = []

        # 최신 실무지침으로 시스템 프롬프트 생성
        system_prompt = build_ai_prompt()

        try:
            if self.provider == "openai":
                return self._analyze_openai(system_prompt, row_data, history)
            elif self.provider == "gemini":
                return self._analyze_gemini(system_prompt, row_data, history)

        except json.JSONDecodeError as e:
            return {
                "status": "ERROR",
                "message": f"AI 응답 파싱 오류: {str(e)}",
                "final_classification": None
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"AI 분석 중 오류: {str(e)}",
                "final_classification": None
            }

    def _analyze_openai(self, system_prompt: str, row_data: str,
                        history: List[Dict]) -> Dict:
        """OpenAI API 호출"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"[현재 검토 중인 거래 데이터]\n{row_data}"}
        ]

        # 대화 기록 추가
        for h in history:
            messages.append(h)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content)

    def _analyze_gemini(self, system_prompt: str, row_data: str,
                        history: List[Dict]) -> Dict:
        """Google Gemini API 호출"""
        # 프롬프트 구성
        prompt = system_prompt + "\n\n" + f"[현재 거래 데이터]\n{row_data}\n"

        for h in history:
            role = "사용자" if h["role"] == "user" else "AI"
            prompt += f"\n{role}: {h['content']}"

        prompt += "\n\n위 정보를 바탕으로 JSON 형식으로 응답하세요:"

        model = genai.GenerativeModel(self.model)
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.3
            }
        )

        return json.loads(response.text)

    def change_model(self, model_name: str):
        """모델 변경"""
        if model_name not in AI_MODELS:
            raise ValueError(f"지원하지 않는 모델: {model_name}")

        model_config = AI_MODELS[model_name]
        self.provider = model_config["provider"]
        self.model = model_config["model"]
        self.model_name = model_name
        self._init_client()

    @staticmethod
    def get_available_models() -> List[str]:
        """사용 가능한 모델 목록"""
        return list(AI_MODELS.keys())

    @staticmethod
    def check_api_keys() -> Dict[str, bool]:
        """API 키 설정 상태 확인"""
        return {
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "gemini": bool(os.getenv("GOOGLE_API_KEY"))
        }
