"""AI Manager - Unified interface for all AI providers"""

from typing import AsyncGenerator, List, Dict, Any, Optional

from app.config import Settings
from app.services.providers import OpenAIProvider, GeminiProvider
from app.services.providers.base import AIProvider


class AIManager:
    """Manages multiple AI providers and handles routing"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.providers: Dict[str, AIProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available providers based on API keys"""

        if self.settings.openai_api_key:
            self.providers["openai"] = OpenAIProvider(self.settings.openai_api_key)
            print(f"[AI Manager] OpenAI provider initialized")

        if self.settings.google_api_key:
            self.providers["google"] = GeminiProvider(self.settings.google_api_key)
            print(f"[AI Manager] Gemini provider initialized")

        # Future providers
        # if self.settings.anthropic_api_key:
        #     self.providers["anthropic"] = AnthropicProvider(self.settings.anthropic_api_key)

    def _get_provider_for_model(self, model: str) -> Optional[AIProvider]:
        """Determine which provider to use based on model name"""

        model_lower = model.lower()

        if "gpt" in model_lower:
            return self.providers.get("openai")
        elif "claude" in model_lower:
            return self.providers.get("anthropic")
        elif "gemini" in model_lower:
            return self.providers.get("google")
        elif "grok" in model_lower:
            return self.providers.get("xai")

        # Default to OpenAI
        return self.providers.get("openai")

    async def generate_stream(
        self,
        user_message: str,
        model: str = "gpt-5-mini",
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response"""

        provider = self._get_provider_for_model(model)

        if not provider:
            yield "[Error: No provider configured for this model]"
            return

        # Build messages
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        # Stream response
        async for token in provider.generate_stream(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        ):
            yield token

    async def generate_stream_with_usage(
        self,
        user_message: str,
        model: str = "gpt-5-mini",
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        images: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate streaming response with token usage tracking"""

        provider = self._get_provider_for_model(model)

        if not provider:
            yield {"type": "error", "content": "[Error: No provider configured for this model]"}
            return

        # Build messages
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        # Stream response with usage tracking
        async for event in provider.generate_stream_with_usage(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            images=images
        ):
            yield event

    async def generate(
        self,
        user_message: str,
        model: str = "gpt-5-mini",
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """Generate non-streaming response"""

        provider = self._get_provider_for_model(model)

        if not provider:
            return "[Error: No provider configured for this model]"

        # Build messages
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        return await provider.generate(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get all available models from configured providers"""

        models = []

        for provider_name, provider in self.providers.items():
            provider_models = provider.get_available_models()
            for model in provider_models:
                model["provider"] = provider_name
                models.append(model)

        return models

    def is_provider_configured(self, provider: str) -> bool:
        """Check if a provider is configured"""
        return provider in self.providers
