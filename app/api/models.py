from typing import List
from fastapi import APIRouter, Depends
from app.db.schemas import ProviderInfo, ModelInfo
from app.services.provider_clients import get_all_providers_info

router = APIRouter(tags=["system"])


@router.get("/providers", response_model=List[ProviderInfo])
async def list_providers():
    """List all supported LLM providers and their models."""
    return get_all_providers_info()


@router.get("/models", response_model=List[ModelInfo])
async def list_models():
    """List all supported models across all providers."""
    providers = get_all_providers_info()
    models = []
    
    for provider in providers:
        for model_name in provider["models"]:
            # Determine max tokens based on model
            max_tokens = 4096  # default
            if "gpt-4" in model_name:
                max_tokens = 8192
            elif "gpt-3.5-turbo-16k" in model_name:
                max_tokens = 16384
            elif "claude-3" in model_name:
                max_tokens = 200000
            elif "claude-2" in model_name:
                max_tokens = 100000
            elif "mistral" in model_name:
                max_tokens = 32768
            
            models.append(ModelInfo(
                name=model_name,
                provider=provider["name"],
                description=f"{provider['description']} - {model_name}",
                max_tokens=max_tokens
            ))
    
    return models


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "teehee-chat-backend"} 