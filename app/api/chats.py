from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.database import get_db
from app.db.models import User, ChatSession, Message
from app.db.schemas import (
    ChatSession as ChatSessionSchema,
    ChatSessionCreate,
    ChatSessionWithMessages
)
from app.api.auth import get_current_user
from uuid import UUID

router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("/", response_model=List[ChatSessionSchema])
async def list_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's chat sessions."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
    )
    sessions = result.scalars().all()
    return sessions


@router.post("/", response_model=ChatSessionSchema)
async def create_chat_session(
    session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new chat session."""
    
    chat_session = ChatSession(
        user_id=current_user.id,
        name=session_data.name or "New Chat"
    )
    
    db.add(chat_session)
    await db.commit()
    await db.refresh(chat_session)
    
    return chat_session


@router.get("/{chat_id}", response_model=ChatSessionWithMessages)
async def get_chat_session(
    chat_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific chat session with its messages."""
    
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(
            ChatSession.id == chat_id,
            ChatSession.user_id == current_user.id
        )
    )
    chat_session = result.scalar_one_or_none()
    
    if not chat_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    return chat_session


@router.delete("/{chat_id}")
async def delete_chat_session(
    chat_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a chat session and all its messages."""
    
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == chat_id,
            ChatSession.user_id == current_user.id
        )
    )
    chat_session = result.scalar_one_or_none()
    
    if not chat_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    await db.delete(chat_session)
    await db.commit()
    
    return {"message": "Chat session deleted successfully"}


@router.patch("/{chat_id}")
async def update_chat_session(
    chat_id: UUID,
    session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a chat session (e.g., change name)."""
    
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == chat_id,
            ChatSession.user_id == current_user.id
        )
    )
    chat_session = result.scalar_one_or_none()
    
    if not chat_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    if session_data.name is not None:
        chat_session.name = session_data.name
    
    await db.commit()
    await db.refresh(chat_session)
    
    return chat_session