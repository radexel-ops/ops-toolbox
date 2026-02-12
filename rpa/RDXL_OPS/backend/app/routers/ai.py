"""
AI Router - System AI endpoints for automation and queries

Uses Google Gemini as main AI (per ai_list.md).
Bridge system uses Claude Code for interactive development.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import logging

from ..services.ai_service import ai_service, AIModel
from ..dependencies import get_current_user
from ..models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


class QueryRequest(BaseModel):
    """AI query request"""
    prompt: str = Field(..., min_length=1, max_length=10000, description="User prompt")
    model: Optional[str] = Field(None, description="Model to use (default: gemini-3-flash-preview)")
    system_prompt: Optional[str] = Field(None, description="System instructions")
    temperature: float = Field(0.7, ge=0, le=1, description="Response randomness")
    max_tokens: int = Field(2048, ge=1, le=8192, description="Max response length")
    stream: bool = Field(False, description="Enable streaming response")


class QueryResponse(BaseModel):
    """AI query response"""
    response: str
    model: str
    usage: Optional[dict] = None


@router.get("/status")
async def get_ai_status(current_user: User = Depends(get_current_user)):
    """
    Get AI service status and available models.
    """
    ai_service.initialize()

    return {
        "available": ai_service.is_available,
        "models": ai_service.available_models,
        "default_model": AIModel.GEMINI_FLASH.value,
    }


@router.post("/query", response_model=QueryResponse)
async def query_ai(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Send a query to the system AI.

    This endpoint is for automation and simple Q&A.
    For interactive development, use the Bridge system with Claude Code.
    """
    ai_service.initialize()

    if not ai_service.is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service unavailable - check API keys in server .env"
        )

    try:
        model = request.model or AIModel.GEMINI_FLASH.value

        response = await ai_service.query(
            prompt=request.prompt,
            model=model,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        logger.info(f"AI query by {current_user.email}: {request.prompt[:50]}...")

        return QueryResponse(
            response=response,
            model=model
        )

    except Exception as e:
        logger.error(f"AI query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI query failed: {str(e)}"
        )


@router.post("/stream")
async def stream_query_ai(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Stream AI response in real-time.

    Returns a streaming response with text chunks.
    """
    ai_service.initialize()

    if not ai_service.is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service unavailable"
        )

    async def generate():
        try:
            async for chunk in ai_service.stream_query(
                prompt=request.prompt,
                model=request.model,
                system_prompt=request.system_prompt
            ):
                yield chunk
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"\n[Error: {str(e)}]"

    return StreamingResponse(
        generate(),
        media_type="text/plain"
    )


@router.get("/models")
async def list_models(current_user: User = Depends(get_current_user)):
    """
    List all supported AI models.
    """
    return {
        "models": [
            {
                "id": AIModel.GEMINI_FLASH.value,
                "name": "Gemini 3 Flash Preview",
                "provider": "google",
                "type": "main",
                "description": "Fast, efficient model for general tasks"
            },
            {
                "id": AIModel.GEMINI_PRO.value,
                "name": "Gemini 3 Pro Preview",
                "provider": "google",
                "type": "sub",
                "description": "More capable model for complex tasks"
            },
            {
                "id": AIModel.GPT_5_2.value,
                "name": "GPT-5.2",
                "provider": "openai",
                "type": "sub",
                "description": "OpenAI's advanced model"
            },
            {
                "id": AIModel.GPT_5_MINI.value,
                "name": "GPT-5 Mini",
                "provider": "openai",
                "type": "sub",
                "description": "OpenAI's efficient model"
            }
        ],
        "note": "For interactive development, use Bridge with Claude Code"
    }
