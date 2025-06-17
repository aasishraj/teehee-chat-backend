from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_db
from app.db.models import User
from app.db.schemas import UserCreate, UserLogin, User as UserSchema, Token
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    verify_token
)
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()


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


@router.post("/signup", response_model=Token)
async def signup(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a new user account."""
    
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = User(
        email=user_data.email,
        sso_id=user_data.sso_id,
        password_hash=get_password_hash(user_data.password) if user_data.password else None
    )
    
    # Validate that either password or sso_id is provided
    if not user_data.password and not user_data.sso_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either password or SSO ID must be provided"
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


@router.post("/signin", response_model=Token)
async def signin(user_credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate user with email and password."""
    
    # Find user by email
    result = await db.execute(select(User).where(User.email == user_credentials.email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Verify password
    if not user.password_hash or not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/sso", response_model=Token)
async def sso_login(sso_data: dict, db: AsyncSession = Depends(get_db)):
    """Handle SSO login/signup."""
    
    # Extract SSO data (this would be customized based on your SSO provider)
    sso_id = sso_data.get("sso_id")
    email = sso_data.get("email")
    
    if not sso_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO ID and email are required"
        )
    
    # Try to find existing user
    result = await db.execute(
        select(User).where((User.sso_id == sso_id) | (User.email == email))
    )
    user = result.scalar_one_or_none()
    
    if user:
        # Update SSO ID if needed
        if not user.sso_id:
            user.sso_id = sso_id
            await db.commit()
    else:
        # Create new user
        user = User(
            email=email,
            sso_id=sso_id,
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