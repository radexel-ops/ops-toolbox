"""
OpenAI Provider Implementation

리팩토링 완료:
- 상세 에러 처리 및 분류
- 재시도 가능 에러 식별
- 로깅 강화
"""

import asyncio
import logging
import tiktoken
from typing import AsyncGenerator, List, Dict, Any
from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError, AuthenticationError

from .base import AIProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """OpenAI API Provider"""

    # 재시도 가능한 에러 코드
    RETRYABLE_ERRORS = (RateLimitError, APIConnectionError, asyncio.TimeoutError)
    MAX_RETRIES = 2
    RETRY_DELAY = 1.0

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncOpenAI(api_key=api_key)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        logger.info("[OpenAI] Provider initialized")

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

    def _classify_error(self, error: Exception) -> Dict[str, Any]:
        """에러를 분류하고 상세 정보 반환"""
        error_info = {
            "type": "unknown",
            "message": str(error),
            "recoverable": False,
            "user_message": "알 수 없는 오류가 발생했습니다."
        }

        if isinstance(error, AuthenticationError):
            error_info.update({
                "type": "authentication",
                "recoverable": False,
                "user_message": "OpenAI API 키가 유효하지 않습니다. 설정을 확인해주세요."
            })
        elif isinstance(error, RateLimitError):
            error_info.update({
                "type": "rate_limit",
                "recoverable": True,
                "user_message": "API 요청 한도에 도달했습니다. 잠시 후 다시 시도합니다."
            })
        elif isinstance(error, APIConnectionError):
            error_info.update({
                "type": "connection",
                "recoverable": True,
                "user_message": "OpenAI 서버 연결에 실패했습니다. 네트워크를 확인해주세요."
            })
        elif isinstance(error, asyncio.TimeoutError):
            error_info.update({
                "type": "timeout",
                "recoverable": True,
                "user_message": "응답 시간이 초과되었습니다. 다시 시도합니다."
            })
        elif isinstance(error, APIError):
            error_info.update({
                "type": "api_error",
                "recoverable": error.status_code in (500, 502, 503, 504),
                "user_message": f"OpenAI API 오류: {error.message}"
            })

        logger.error(f"[OpenAI] Error classified: {error_info['type']} - {error_info['message']}")
        return error_info

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

        # 재시도 로직
        last_error = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                # API 파라미터 구성
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

                logger.debug(f"[OpenAI] Request: model={model}, attempt={attempt + 1}")

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

                # 성공적으로 완료
                logger.debug(f"[OpenAI] Response completed: {len(output_text)} chars")
                return

            except self.RETRYABLE_ERRORS as e:
                last_error = e
                error_info = self._classify_error(e)

                if attempt < self.MAX_RETRIES:
                    logger.warning(f"[OpenAI] Retryable error on attempt {attempt + 1}: {error_info['type']}")
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))  # 지수 백오프
                    continue
                else:
                    logger.error(f"[OpenAI] Max retries exceeded: {error_info['type']}")
                    yield {
                        "type": "error",
                        "content": error_info['user_message'],
                        "error_type": error_info['type'],
                        "recoverable": error_info['recoverable']
                    }
                    return

            except Exception as e:
                error_info = self._classify_error(e)
                logger.error(f"[OpenAI] Non-retryable error: {error_info['type']}")
                yield {
                    "type": "error",
                    "content": error_info['user_message'],
                    "error_type": error_info['type'],
                    "recoverable": error_info['recoverable']
                }
                return

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-5-mini",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response from OpenAI"""

        for attempt in range(self.MAX_RETRIES + 1):
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

                return

            except self.RETRYABLE_ERRORS as e:
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"[OpenAI] Retrying after error: {e}")
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                else:
                    error_info = self._classify_error(e)
                    yield f"[Error: {error_info['user_message']}]"
                    return

            except Exception as e:
                error_info = self._classify_error(e)
                yield f"[Error: {error_info['user_message']}]"
                return

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-5-mini",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> str:
        """Generate non-streaming response from OpenAI"""

        for attempt in range(self.MAX_RETRIES + 1):
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

            except self.RETRYABLE_ERRORS as e:
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"[OpenAI] Retrying after error: {e}")
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                else:
                    error_info = self._classify_error(e)
                    return f"[Error: {error_info['user_message']}]"

            except Exception as e:
                error_info = self._classify_error(e)
                return f"[Error: {error_info['user_message']}]"

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Return available OpenAI models"""
        return [
            {"id": "gpt-5-mini", "name": "GPT-5 Mini", "context": 128000},
            {"id": "gpt-5.2", "name": "GPT-5.2", "context": 128000},
        ]
