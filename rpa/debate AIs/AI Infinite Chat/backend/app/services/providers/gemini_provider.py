"""Google Gemini Provider Implementation"""

from typing import AsyncGenerator, List, Dict, Any
import google.generativeai as genai
import base64

from .base import AIProvider


class GeminiProvider(AIProvider):
    """Google Gemini API Provider"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        genai.configure(api_key=api_key)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (roughly 4 chars per token for multilingual)"""
        return len(text) // 3  # Conservative estimate for Korean/English mix

    def _prepare_image_parts(self, images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """이미지를 Gemini API 형식으로 변환"""
        parts = []
        for img in images:
            if img.get("base64"):
                parts.append({
                    "inline_data": {
                        "mime_type": img.get("content_type", "image/jpeg"),
                        "data": img.get("base64")
                    }
                })
        return parts

    @property
    def provider_name(self) -> str:
        return "google"

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = "gemini-3-flash-preview",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response from Gemini"""

        try:
            # Gemini 모델 생성
            gemini_model = genai.GenerativeModel(model)

            # 메시지를 Gemini 형식으로 변환
            # Gemini는 system prompt를 별도로 처리
            system_prompt = ""
            chat_history = []
            current_message = ""

            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    system_prompt = content
                elif role == "user":
                    current_message = content
                elif role == "assistant":
                    # 이전 대화 기록으로 추가
                    chat_history.append({"role": "user", "parts": [content]})
                    chat_history.append({"role": "model", "parts": ["understood"]})

            # 프롬프트 구성
            parts = []
            if system_prompt:
                parts.append(f"[System Instructions]\n{system_prompt}\n\n")
            parts.append(current_message)

            full_prompt = "".join(parts)

            # 스트리밍 응답 생성
            response = gemini_model.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
                stream=True
            )

            for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            yield f"[Error: {str(e)}]"

    async def generate_stream_with_usage(
        self,
        messages: List[Dict[str, str]],
        model: str = "gemini-3-flash-preview",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        images: List[Dict[str, Any]] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate streaming response with token usage tracking"""

        output_text = ""

        try:
            gemini_model = genai.GenerativeModel(model)

            # Convert messages to Gemini format
            system_prompt = ""
            current_message = ""

            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    system_prompt = content
                elif role == "user":
                    current_message = content

            # Build prompt parts (text + images)
            content_parts = []
            if system_prompt:
                content_parts.append(f"[System Instructions]\n{system_prompt}\n\n")
            content_parts.append(current_message)

            full_prompt = "".join(content_parts)

            # Estimate input tokens
            input_tokens = self._estimate_tokens(full_prompt)

            # 이미지가 있으면 멀티모달 콘텐츠 생성
            if images:
                image_parts = self._prepare_image_parts(images)
                # 텍스트와 이미지를 함께 전달
                prompt_content = [full_prompt] + image_parts
            else:
                prompt_content = full_prompt

            # Generate streaming response
            response = gemini_model.generate_content(
                prompt_content,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
                stream=True
            )

            for chunk in response:
                if chunk.text:
                    output_text += chunk.text
                    yield {"type": "token", "content": chunk.text}

            # Calculate output tokens and update totals
            output_tokens = self._estimate_tokens(output_text)
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

            yield {
                "type": "usage",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_input": self.total_input_tokens,
                "total_output": self.total_output_tokens
            }

        except Exception as e:
            yield {"type": "error", "content": f"[Error: {str(e)}]"}

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "gemini-3-flash-preview",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> str:
        """Generate non-streaming response from Gemini"""

        try:
            gemini_model = genai.GenerativeModel(model)

            # 메시지를 Gemini 형식으로 변환
            system_prompt = ""
            current_message = ""

            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    system_prompt = content
                elif role == "user":
                    current_message = content

            # 프롬프트 구성
            parts = []
            if system_prompt:
                parts.append(f"[System Instructions]\n{system_prompt}\n\n")
            parts.append(current_message)

            full_prompt = "".join(parts)

            response = gemini_model.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            )

            return response.text

        except Exception as e:
            return f"[Error: {str(e)}]"

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Return available Gemini models"""
        return [
            {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash", "context": 1000000},
            {"id": "gemini-3-pro-preview", "name": "Gemini 3 Pro", "context": 2000000},
        ]
