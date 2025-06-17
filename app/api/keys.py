from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_db
from app.db.models import User, ProviderKey
from app.db.schemas import ProviderKey as ProviderKeySchema, ProviderKeyCreate
from app.api.auth import get_current_user
from app.core.security import encrypt_api_key, decrypt_api_key
from uuid import UUID

router = APIRouter(prefix="/user/keys", tags=["api-keys"])


@router.get("/", response_model=List[ProviderKeySchema])
async def list_provider_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's provider API keys."""
    result = await db.execute(
        select(ProviderKey).where(ProviderKey.user_id == current_user.id)
    )
    keys = result.scalars().all()
    return keys


@router.post("/", response_model=ProviderKeySchema)
async def add_provider_key(
    key_data: ProviderKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a new provider API key."""
    
    # Check if user already has a key for this provider
    result = await db.execute(
        select(ProviderKey).where(
            ProviderKey.user_id == current_user.id,
            ProviderKey.provider_name == key_data.provider_name
        )
    )
    existing_key = result.scalar_one_or_none()
    
    if existing_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API key for {key_data.provider_name} already exists"
        )
    
    # Validate provider name
    valid_providers = ["openai", "anthropic", "mistral"]
    if key_data.provider_name not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider. Must be one of: {', '.join(valid_providers)}"
        )
    
    # Encrypt and store the API key
    encrypted_key = encrypt_api_key(key_data.api_key)
    
    provider_key = ProviderKey(
        user_id=current_user.id,
        provider_name=key_data.provider_name,
        encrypted_api_key=encrypted_key
    )
    
    db.add(provider_key)
    await db.commit()
    await db.refresh(provider_key)
    
    return provider_key


@router.delete("/{key_id}")
async def delete_provider_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a provider API key."""
    
    # Find the key
    result = await db.execute(
        select(ProviderKey).where(
            ProviderKey.id == key_id,
            ProviderKey.user_id == current_user.id
        )
    )
    provider_key = result.scalar_one_or_none()
    
    if not provider_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    await db.delete(provider_key)
    await db.commit()
    
    return {"message": "API key deleted successfully"}


@router.get("/{provider_name}/decrypt")
async def get_decrypted_key(
    provider_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get decrypted API key for internal use (protected endpoint)."""
    
    # This endpoint would typically be protected further or used internally
    result = await db.execute(
        select(ProviderKey).where(
            ProviderKey.user_id == current_user.id,
            ProviderKey.provider_name == provider_name
        )
    )
    provider_key = result.scalar_one_or_none()
    
    if not provider_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No API key found for {provider_name}"
        )
    
    try:
        decrypted_key = decrypt_api_key(provider_key.encrypted_api_key)
        return {"api_key": decrypted_key}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt API key"
        )