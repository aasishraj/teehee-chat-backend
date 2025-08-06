from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import requests
from app.db.database import get_db
from app.db.models import User
from app.db.schemas import UserCreate, User as UserSchema, Token
from app.core.security import (
    create_access_token,
    verify_token
)
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()


def verify_google_token(token: str) -> dict:
    """Verify Google ID token and return user info."""
    try:
        response = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={token}")
        response.raise_for_status()
        idinfo = response.json()

        # Check for error in response
        if "error" in idinfo:
            raise ValueError(f"Token validation error: {idinfo['error']}")

        # Verify the token is for our application
        if settings.google_client_id and idinfo.get("aud") != settings.google_client_id:
            raise ValueError("Unrecognized client ID")
            
        return idinfo
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {str(e)}"
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user."""
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    email: str = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


@router.post("/google-sso", response_model=Token)
async def google_sso_login(sso_data: dict, db: AsyncSession = Depends(get_db)):
    """Handle Google SSO login/signup."""
    
    # Extract Google ID token from request
    google_token = sso_data.get("token")
    if not google_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google token is required"
        )
    
    # Verify Google token and extract user info
    try:
        google_user_info = verify_google_token(google_token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to verify Google token: {str(e)}"
        )
    
    # Extract user information from Google token
    email = google_user_info.get("email")
    google_user_id = google_user_info.get("sub")  # Google's unique user ID
    name = google_user_info.get("name")
    
    if not email or not google_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and user ID are required from Google token"
        )
    
    # Try to find existing user by email or Google user ID
    result = await db.execute(
        select(User).where((User.sso_id == google_user_id) | (User.email == email))
    )
    user = result.scalar_one_or_none()
    
    if user:
        # Update SSO ID if needed (in case user was created with email but no SSO ID)
        if not user.sso_id:
            user.sso_id = google_user_id
            await db.commit()
    else:
        # Create new user
        print(f"Creating new user: {email} with SSO ID: {google_user_id}")
        user = User(
            email=email,
            sso_id=google_user_id,
            password_hash=None
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/session", response_model=UserSchema)
async def get_session(current_user: User = Depends(get_current_user)):
    """Get current session information."""
    return current_user


@router.post("/logout")
async def logout():
    """Logout user (client should discard token)."""
    return {"message": "Successfully logged out"}