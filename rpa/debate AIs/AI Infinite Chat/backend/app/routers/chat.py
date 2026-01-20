"""Chat API Router"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()


class Message(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = "gpt-5-mini"
    history: Optional[List[Message]] = []


class ChatResponse(BaseModel):
    response: str
    model: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Non-streaming chat endpoint (for testing)"""
    # This is a simple endpoint for testing
    # The main chat uses WebSocket for streaming
    return ChatResponse(
        response=f"Echo: {request.message}",
        model=request.model
    )


@router.get("/models")
async def get_models():
    """Get available AI models"""
    return {
        "models": [
            # OpenAI
            {"id": "gpt-5-mini", "name": "GPT-5 Mini (Fast)", "provider": "openai"},
            {"id": "gpt-5.2", "name": "GPT-5.2", "provider": "openai"},
            # Google Gemini
            {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash (Fast)", "provider": "google"},
            {"id": "gemini-3-pro-preview", "name": "Gemini 3 Pro", "provider": "google"},
        ]
    }
