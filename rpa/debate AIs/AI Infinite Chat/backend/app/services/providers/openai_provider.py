"""OpenAI Provider Implementation"""

import asyncio
import tiktoken
from typing import AsyncGenerator, List, Dict, Any, Tuple
from openai import AsyncOpenAI

from .base import AIProvider


class OpenAIProvider(AIProvider):
    """OpenAI API Provider"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncOpenAI(api_key=api_key)
        # 토큰 사용량 추적
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    @property
    def provider_name(self) -> str:
        return "openai"

    def count_tokens(self, text: str, model: str = "gpt-5-mini") -> int:
        """텍스트의 토큰 수 계산"""
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    def count_messages_tokens(self, messages: List[Dict[str, str]], model: str = "gpt-5-mini") -> int:
        """메시지 리스트의 토큰 수 계산"""
        total = 0
        for msg in messages:
            total += self.count_tokens(msg.get("content", ""), model)
            total += 4  # 메시지 오버헤드
        return total + 2  # 시작/끝 토큰

    def _format_messages_with_images(
        self,
        messages: List[Dict[str, str]],
        images: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """이미지가 있는 경우 메시지를 Vision API 형식으로 변환"""
        if not images:
            return messages

        # 마지막 사용자 메시지에 이미지 추가
        formatted = []
        for i, msg in enumerate(messages):
            if i == len(messages) - 1 and msg.get("role") == "user":
                # 마지막 사용자 메시지에 이미지 추가
                content = [{"type": "text", "text": msg.get("content", "")}]
                for img in images:
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{img.get('content_type', 'image/jpeg')};base64,{img.get('base64', '')}"
                        }
                    })
                formatted.append({"role": "user", "content": content})
            else:
                formatted.append(msg)

        return formatted

    def _is_reasoning_model(self, model: str) -> bool:
        """Check if model is a reasoning model (o1, gpt-5, etc.) that has parameter restrictions"""
        model_lower = model.lower()
        return any(x in model_lower for x in ['o1', 'gpt-5', 'reasoning'])

    async def generate_stream_with_usage(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-5-mini",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        images: List[Dict[str, Any]] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate streaming response with token usage tracking"""

        output_text = ""
        usage_received = False

        # 이미지가 있으면 메시지 형식 변환
        formatted_messages = self._format_messages_with_images(messages, images)

        try:
            # Reasoning models (o1, gpt-5) don't support temperature
            api_params = {
                "model": model,
                "messages": formatted_messages,
                "max_completion_tokens": max_tokens,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            if not self._is_reasoning_model(model):
                api_params["temperature"] = temperature
            api_params.update(kwargs)

            stream = await self.client.chat.completions.create(**api_params)

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    output_text += content
                    yield {"type": "token", "content": content}

                # Final chunk contains usage info
                if hasattr(chunk, 'usage') and chunk.usage:
                    input_tokens = chunk.usage.prompt_tokens
                    output_tokens = chunk.usage.completion_tokens
                    self.total_input_tokens += input_tokens
                    self.total_output_tokens += output_tokens
                    usage_received = True
                    yield {
                        "type": "usage",
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_input": self.total_input_tokens,
                        "total_output": self.total_output_tokens
                    }

            # Fallback: estimate tokens if stream_options not supported
            if not usage_received and output_text:
                input_tokens = self.count_messages_tokens(messages, model)
                output_tokens = self.count_tokens(output_text, model)
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

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-5-mini",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response from OpenAI"""

        try:
            api_params = {
                "model": model,
                "messages": messages,
                "max_completion_tokens": max_tokens,
                "stream": True,
            }
            if not self._is_reasoning_model(model):
                api_params["temperature"] = temperature
            api_params.update(kwargs)

            stream = await self.client.chat.completions.create(**api_params)

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            yield f"[Error: {str(e)}]"

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-5-mini",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> str:
        """Generate non-streaming response from OpenAI"""

        try:
            api_params = {
                "model": model,
                "messages": messages,
                "max_completion_tokens": max_tokens,
            }
            if not self._is_reasoning_model(model):
                api_params["temperature"] = temperature
            api_params.update(kwargs)

            response = await self.client.chat.completions.create(**api_params)

            return response.choices[0].message.content

        except Exception as e:
            return f"[Error: {str(e)}]"

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Return available OpenAI models"""
        return [
            {"id": "gpt-5-mini", "name": "GPT-5 Mini", "context": 128000},
            {"id": "gpt-5.2", "name": "GPT-5.2", "context": 128000},
        ]
