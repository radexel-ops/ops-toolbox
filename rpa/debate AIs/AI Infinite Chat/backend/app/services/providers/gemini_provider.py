"""
Google Gemini Provider Implementation

리팩토링 완료:
- 상세 에러 처리 및 분류
- 재시도 가능 에러 식별
- 로깅 강화
- 비동기 처리 수정 (동기 SDK를 asyncio로 래핑)
"""

import asyncio
import logging
from typing import AsyncGenerator, List, Dict, Any
from functools import partial
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from .base import AIProvider

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """Google Gemini API Provider"""

    # 재시도 가능한 에러 타입
    RETRYABLE_ERRORS = (
        google_exceptions.ServiceUnavailable,
        google_exceptions.ResourceExhausted,
        google_exceptions.DeadlineExceeded,
        asyncio.TimeoutError,
        ConnectionError,
    )
    MAX_RETRIES = 2
    RETRY_DELAY = 1.0

    def __init__(self, api_key: str):
        super().__init__(api_key)
        genai.configure(api_key=api_key)
        logger.info("[Gemini] Provider initialized")

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

    def _classify_error(self, error: Exception) -> Dict[str, Any]:
        """에러를 분류하고 상세 정보 반환"""
        error_info = {
            "type": "unknown",
            "message": str(error),
            "recoverable": False,
            "user_message": "알 수 없는 오류가 발생했습니다."
        }

        if isinstance(error, google_exceptions.InvalidArgument):
            error_info.update({
                "type": "invalid_argument",
                "recoverable": False,
                "user_message": "잘못된 요청입니다. 입력을 확인해주세요."
            })
        elif isinstance(error, google_exceptions.PermissionDenied):
            error_info.update({
                "type": "permission_denied",
                "recoverable": False,
                "user_message": "Gemini API 키가 유효하지 않거나 권한이 없습니다."
            })
        elif isinstance(error, google_exceptions.ResourceExhausted):
            error_info.update({
                "type": "rate_limit",
                "recoverable": True,
                "user_message": "API 요청 한도에 도달했습니다. 잠시 후 다시 시도합니다."
            })
        elif isinstance(error, google_exceptions.ServiceUnavailable):
            error_info.update({
                "type": "service_unavailable",
                "recoverable": True,
                "user_message": "Gemini 서비스가 일시적으로 불가합니다. 다시 시도합니다."
            })
        elif isinstance(error, google_exceptions.DeadlineExceeded):
            error_info.update({
                "type": "timeout",
                "recoverable": True,
                "user_message": "응답 시간이 초과되었습니다. 다시 시도합니다."
            })
        elif isinstance(error, asyncio.TimeoutError):
            error_info.update({
                "type": "timeout",
                "recoverable": True,
                "user_message": "응답 시간이 초과되었습니다. 다시 시도합니다."
            })
        elif isinstance(error, ConnectionError):
            error_info.update({
                "type": "connection",
                "recoverable": True,
                "user_message": "네트워크 연결에 실패했습니다. 네트워크를 확인해주세요."
            })
        elif "safety" in str(error).lower() or "blocked" in str(error).lower():
            error_info.update({
                "type": "safety_filter",
                "recoverable": False,
                "user_message": "안전 필터에 의해 응답이 차단되었습니다."
            })

        logger.error(f"[Gemini] Error classified: {error_info['type']} - {error_info['message']}")
        return error_info

    def _sync_generate_stream(
        self,
        model: str,
        full_prompt: str,
        temperature: float,
        max_tokens: int
    ) -> List[str]:
        """동기적으로 스트리밍 응답 생성 (별도 스레드에서 실행)"""
        try:
            logger.info(f"[Gemini] _sync_generate_stream: model={model}, temp={temperature}, max_tokens={max_tokens}")
            logger.info(f"[Gemini] prompt length: {len(full_prompt)}")

            gemini_model = genai.GenerativeModel(model)
            response = gemini_model.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
                stream=True
            )
            # 모든 청크를 수집하여 반환
            chunks = []
            for chunk in response:
                if chunk.text:
                    chunks.append(chunk.text)
            logger.info(f"[Gemini] Successfully generated {len(chunks)} chunks")
            return chunks
        except Exception as e:
            logger.error(f"[Gemini] _sync_generate_stream ERROR: {type(e).__name__}: {e}")
            raise

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = "gemini-3-flash-preview",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response from Gemini"""

        for attempt in range(self.MAX_RETRIES + 1):
            try:
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

                logger.debug(f"[Gemini] Request: model={model}, attempt={attempt + 1}")

                # 동기 코드를 별도 스레드에서 실행
                loop = asyncio.get_event_loop()
                chunks = await loop.run_in_executor(
                    None,
                    partial(self._sync_generate_stream, model, full_prompt, temperature, max_tokens)
                )

                # 수집된 청크들을 yield
                for chunk in chunks:
                    yield chunk

                return

            except self.RETRYABLE_ERRORS as e:
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"[Gemini] Retrying after error: {e}")
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

    def _sync_generate_stream_with_images(
        self,
        model: str,
        prompt_content,
        temperature: float,
        max_tokens: int
    ) -> List[str]:
        """동기적으로 스트리밍 응답 생성 (이미지 포함, 별도 스레드에서 실행)"""
        try:
            logger.info(f"[Gemini] _sync_generate_stream_with_images: model={model}, temp={temperature}, max_tokens={max_tokens}")
            logger.info(f"[Gemini] prompt_content type: {type(prompt_content)}, length: {len(str(prompt_content)[:200])}")

            gemini_model = genai.GenerativeModel(model)
            response = gemini_model.generate_content(
                prompt_content,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
                stream=True
            )
            chunks = []
            for chunk in response:
                if chunk.text:
                    chunks.append(chunk.text)
            logger.info(f"[Gemini] Successfully generated {len(chunks)} chunks")
            return chunks
        except Exception as e:
            logger.error(f"[Gemini] _sync_generate_stream_with_images ERROR: {type(e).__name__}: {e}")
            raise

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

        for attempt in range(self.MAX_RETRIES + 1):
            try:
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

                # Build prompt parts
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
                    prompt_content = [full_prompt] + image_parts
                else:
                    prompt_content = full_prompt

                logger.debug(f"[Gemini] Request: model={model}, attempt={attempt + 1}, has_images={bool(images)}")

                # 동기 코드를 별도 스레드에서 실행
                loop = asyncio.get_event_loop()
                chunks = await loop.run_in_executor(
                    None,
                    partial(self._sync_generate_stream_with_images, model, prompt_content, temperature, max_tokens)
                )

                # 수집된 청크들을 yield
                for chunk in chunks:
                    output_text += chunk
                    yield {"type": "token", "content": chunk}

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

                logger.debug(f"[Gemini] Response completed: {len(output_text)} chars")
                return

            except self.RETRYABLE_ERRORS as e:
                if attempt < self.MAX_RETRIES:
                    error_info = self._classify_error(e)
                    logger.warning(f"[Gemini] Retryable error on attempt {attempt + 1}: {error_info['type']}")
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    output_text = ""  # Reset for retry
                    continue
                else:
                    error_info = self._classify_error(e)
                    logger.error(f"[Gemini] Max retries exceeded: {error_info['type']}")
                    yield {
                        "type": "error",
                        "content": error_info['user_message'],
                        "error_type": error_info['type'],
                        "recoverable": error_info['recoverable']
                    }
                    return

            except Exception as e:
                error_info = self._classify_error(e)
                logger.error(f"[Gemini] Non-retryable error: {error_info['type']}")
                yield {
                    "type": "error",
                    "content": error_info['user_message'],
                    "error_type": error_info['type'],
                    "recoverable": error_info['recoverable']
                }
                return

    def _sync_generate(
        self,
        model: str,
        full_prompt: str,
        temperature: float,
        max_tokens: int
    ) -> str:
        """동기적으로 응답 생성 (별도 스레드에서 실행)"""
        gemini_model = genai.GenerativeModel(model)
        response = gemini_model.generate_content(
            full_prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        )
        return response.text

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "gemini-3-flash-preview",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> str:
        """Generate non-streaming response from Gemini"""

        for attempt in range(self.MAX_RETRIES + 1):
            try:
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

                # 동기 코드를 별도 스레드에서 실행
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    partial(self._sync_generate, model, full_prompt, temperature, max_tokens)
                )

                return result

            except self.RETRYABLE_ERRORS as e:
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"[Gemini] Retrying after error: {e}")
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                else:
                    error_info = self._classify_error(e)
                    return f"[Error: {error_info['user_message']}]"

            except Exception as e:
                error_info = self._classify_error(e)
                return f"[Error: {error_info['user_message']}]"

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Return available Gemini models"""
        return [
            {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash", "context": 1000000},
            {"id": "gemini-3-pro-preview", "name": "Gemini 3 Pro", "context": 2000000},
        ]
