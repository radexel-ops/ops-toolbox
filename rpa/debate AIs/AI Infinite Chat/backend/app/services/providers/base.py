"""Base AI Provider Abstract Class"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any, Optional


class AIProvider(ABC):
    """Abstract base class for AI providers"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        # Token usage tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider name"""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response"""
        pass

    async def generate_stream_with_usage(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate streaming response with token usage tracking.

        Yields dicts with type: 'token' for content, 'usage' for token counts.
        Default implementation wraps generate_stream without actual usage tracking.
        Providers should override this for accurate token counting.
        """
        async for token in self.generate_stream(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        ):
            yield {"type": "token", "content": token}

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> str:
        """Generate non-streaming response"""
        pass

    @abstractmethod
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Return list of available models for this provider"""
        pass

    def get_total_usage(self) -> Dict[str, int]:
        """Return total token usage for this provider"""
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens
        }
