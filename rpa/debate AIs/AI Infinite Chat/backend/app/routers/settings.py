"""Settings API Router"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List, Optional
from app.config import get_settings

router = APIRouter()


class APIKeysUpdate(BaseModel):
    """여러 제공사의 API 키를 한 번에 업데이트"""
    openai: Optional[str] = None
    google: Optional[str] = None
    anthropic: Optional[str] = None
    xai: Optional[str] = None


class SettingsResponse(BaseModel):
    configured_providers: List[str]
    default_model: str
    available_models: List[Dict]


# 사용자별 API 키 저장 (세션 기반, 추후 DB로 전환)
# 실제 프로덕션에서는 암호화 저장 필요
session_api_keys: Dict[str, str] = {}


def get_api_keys() -> Dict[str, str]:
    """현재 세션의 API 키 반환"""
    return session_api_keys.copy()


def set_api_keys(keys: Dict[str, str]):
    """API 키 설정"""
    global session_api_keys
    for provider, key in keys.items():
        if key:
            session_api_keys[provider] = key


@router.get("/settings", response_model=SettingsResponse)
async def get_settings_endpoint():
    """현재 설정 조회"""
    settings = get_settings()

    # 세션 키 + 환경 변수 키 모두 확인
    configured = set()

    # 세션에 저장된 키
    for provider, key in session_api_keys.items():
        if key:
            configured.add(provider)

    # 환경 변수에 설정된 키
    if settings.openai_api_key:
        configured.add('openai')
    if settings.google_api_key:
        configured.add('google')
    if settings.anthropic_api_key:
        configured.add('anthropic')

    available_models = [
        {"id": "gpt-5-mini", "name": "GPT-5 Mini", "provider": "openai"},
        {"id": "gpt-5.2", "name": "GPT-5.2", "provider": "openai"},
        {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash", "provider": "google"},
        {"id": "gemini-3-pro-preview", "name": "Gemini 3 Pro", "provider": "google"},
    ]

    return SettingsResponse(
        configured_providers=list(configured),
        default_model="gpt-5-mini",
        available_models=available_models
    )


@router.post("/settings/api-keys")
async def update_api_keys(keys: APIKeysUpdate):
    """API 키 일괄 업데이트"""
    keys_dict = keys.model_dump(exclude_none=True)
    set_api_keys(keys_dict)

    configured = [provider for provider, key in session_api_keys.items() if key]
    return {
        "status": "ok",
        "configured_providers": configured
    }


@router.delete("/settings/api-keys/{provider}")
async def delete_api_key(provider: str):
    """특정 제공사의 API 키 삭제"""
    if provider in session_api_keys:
        del session_api_keys[provider]
    return {"status": "ok", "provider": provider}
