from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_db
from app.db.models import User, ChatSession, Message
from app.db.schemas import (
    Message as MessageSchema,
    MessageCreate,
    MessageStream
)
from app.api.auth import get_current_user
from uuid import UUID

router = APIRouter(prefix="/chats", tags=["messages"])


@router.get("/{chat_id}/messages", response_model=List[MessageSchema])
async def list_messages(
    chat_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List messages in a chat session."""
    
    # Verify chat session belongs to user
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
    
    # Get messages ordered by timestamp
    result = await db.execute(
        select(Message)
        .where(Message.chat_session_id == chat_id)
        .order_by(Message.timestamp)
    )
    messages = result.scalars().all()
    
    return messages


@router.post("/{chat_id}/messages", response_model=MessageSchema)
async def create_message(
    chat_id: UUID,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new message in a chat session."""
    
    # Verify chat session belongs to user
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
    
    # Validate parent message if specified
    if message_data.parent_message_id:
        result = await db.execute(
            select(Message).where(
                Message.id == message_data.parent_message_id,
                Message.chat_session_id == chat_id
            )
        )
        parent_message = result.scalar_one_or_none()
        
        if not parent_message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent message not found in this chat session"
            )
    
    # Create the message
    message = Message(
        chat_session_id=chat_id,
        parent_message_id=message_data.parent_message_id,
        role=message_data.role,
        content=message_data.content if isinstance(message_data.content, dict) else {"text": str(message_data.content)},
        is_partial=False
    )
    
    db.add(message)
    await db.commit()
    await db.refresh(message)
    
    return message


@router.patch("/messages/{message_id}")
async def edit_message(
    message_id: UUID,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Edit an existing message."""
    
    # Get the message and verify ownership through chat session
    result = await db.execute(
        select(Message)
        .join(ChatSession)
        .where(
            Message.id == message_id,
            ChatSession.user_id == current_user.id
        )
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found or not accessible"
        )
    
    # Only allow editing user messages
    if message.role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only user messages can be edited"
        )
    
    # Update the message content
    message.content = message_data.content if isinstance(message_data.content, dict) else {"text": str(message_data.content)}
    
    await db.commit()
    await db.refresh(message)
    
    return message


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a message (soft delete by marking as deleted)."""
    
    # Get the message and verify ownership
    result = await db.execute(
        select(Message)
        .join(ChatSession)
        .where(
            Message.id == message_id,
            ChatSession.user_id == current_user.id
        )
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found or not accessible"
        )
    
    # Mark as deleted instead of hard delete to preserve conversation structure
    message.content = {"text": "[Message deleted]", "deleted": True}
    
    await db.commit()
    
    return {"message": "Message deleted successfully"} 