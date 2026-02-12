"""
AI Service - System AI for automation and simple queries

Uses Google Gemini as the main AI model (ai_list.md reference).
- Main: gemini-3-flash-preview
- Sub: gemini-3-pro-preview, gpt-5.2, gpt-5-mini
"""

import os
import logging
from typing import Optional, AsyncGenerator
from enum import Enum

logger = logging.getLogger(__name__)


class AIModel(str, Enum):
    """Available AI models"""
    # Google Gemini (Main)
    GEMINI_FLASH = "gemini-3-flash-preview"
    GEMINI_PRO = "gemini-3-pro-preview"
    # OpenAI (Sub)
    GPT_5_2 = "gpt-5.2"
    GPT_5_MINI = "gpt-5-mini"


class AIService:
    """
    System AI service for automation and simple Q&A.

    This is separate from Bridge (Claude Code) which handles
    interactive development conversations.
    """

    def __init__(self):
        self._gemini_model = None
        self._openai_client = None
        self._initialized = False

    def _init_gemini(self):
        """Initialize Google Gemini client"""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY not set, Gemini unavailable")
            return False

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._gemini_model = genai.GenerativeModel(AIModel.GEMINI_FLASH.value)
            logger.info(f"Gemini initialized with model: {AIModel.GEMINI_FLASH.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            return False

    def _init_openai(self):
        """Initialize OpenAI client"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, OpenAI unavailable")
            return False

        try:
            from openai import OpenAI
            self._openai_client = OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI: {e}")
            return False

    def initialize(self):
        """Initialize AI clients"""
        if self._initialized:
            return

        gemini_ok = self._init_gemini()
        openai_ok = self._init_openai()

        self._initialized = True

        if not gemini_ok and not openai_ok:
            logger.warning("No AI services available - check API keys in .env")

    @property
    def is_available(self) -> bool:
        """Check if any AI service is available"""
        return self._gemini_model is not None or self._openai_client is not None

    @property
    def available_models(self) -> list:
        """Get list of available models"""
        models = []
        if self._gemini_model:
            models.extend([AIModel.GEMINI_FLASH.value, AIModel.GEMINI_PRO.value])
        if self._openai_client:
            models.extend([AIModel.GPT_5_2.value, AIModel.GPT_5_MINI.value])
        return models

    async def query(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """
        Send a query to the AI model.

        Args:
            prompt: User's question or instruction
            model: Model to use (default: gemini-3-flash-preview)
            system_prompt: System instructions (optional)
            temperature: Response randomness (0-1)
            max_tokens: Maximum response length

        Returns:
            AI response text
        """
        if not self._initialized:
            self.initialize()

        # Default to Gemini Flash
        model = model or AIModel.GEMINI_FLASH.value

        # Use Gemini for gemini models
        if model.startswith("gemini"):
            return await self._query_gemini(prompt, system_prompt, temperature, max_tokens)

        # Use OpenAI for GPT models
        if model.startswith("gpt"):
            return await self._query_openai(prompt, model, system_prompt, temperature, max_tokens)

        raise ValueError(f"Unknown model: {model}")

    async def _query_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Query Gemini model"""
        if not self._gemini_model:
            raise RuntimeError("Gemini not initialized - check GOOGLE_API_KEY")

        try:
            # Combine system prompt if provided
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            # Generate response
            response = self._gemini_model.generate_content(
                full_prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                }
            )

            return response.text

        except Exception as e:
            logger.error(f"Gemini query failed: {e}")
            raise

    async def _query_openai(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Query OpenAI model"""
        if not self._openai_client:
            raise RuntimeError("OpenAI not initialized - check OPENAI_API_KEY")

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self._openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI query failed: {e}")
            raise

    async def stream_query(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream a query response (for real-time output).

        Yields:
            Text chunks as they are generated
        """
        if not self._initialized:
            self.initialize()

        model = model or AIModel.GEMINI_FLASH.value

        if model.startswith("gemini"):
            async for chunk in self._stream_gemini(prompt, system_prompt):
                yield chunk
        elif model.startswith("gpt"):
            async for chunk in self._stream_openai(prompt, model, system_prompt):
                yield chunk
        else:
            raise ValueError(f"Unknown model: {model}")

    async def _stream_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str]
    ) -> AsyncGenerator[str, None]:
        """Stream from Gemini"""
        if not self._gemini_model:
            raise RuntimeError("Gemini not initialized")

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        response = self._gemini_model.generate_content(
            full_prompt,
            stream=True
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text

    async def _stream_openai(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str]
    ) -> AsyncGenerator[str, None]:
        """Stream from OpenAI"""
        if not self._openai_client:
            raise RuntimeError("OpenAI not initialized")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = self._openai_client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# Global service instance
ai_service = AIService()
