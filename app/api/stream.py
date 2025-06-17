from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_db
from app.db.models import User, ChatSession, Message, ProviderKey
from app.db.schemas import MessageStream, StreamResponse
from app.api.auth import get_current_user
from app.core.security import decrypt_api_key
from app.utils.streaming import (
    stream_manager,
    stream_llm_response,
    abort_stream,
    continue_stream
)
from app.services.provider_clients import get_provider
from uuid import UUID
import json

router = APIRouter(prefix="/stream", tags=["streaming"])


@router.websocket("/{chat_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    chat_id: UUID,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """WebSocket endpoint for real-time streaming."""
    
    # Verify token and get user
    from app.core.security import verify_token
    payload = verify_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    email = payload.get("sub")
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        await websocket.close(code=4001, reason="User not found")
        return
    
    # Verify chat session
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == chat_id,
            ChatSession.user_id == user.id
        )
    )
    chat_session = result.scalar_one_or_none()
    
    if not chat_session:
        await websocket.close(code=4004, reason="Chat session not found")
        return
    
    # Connect to stream manager
    session_key = str(chat_id)
    await stream_manager.connect(websocket, session_key)
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "stream_message":
                await handle_stream_message(
                    chat_id, message_data, user, db, websocket
                )
            elif message_data.get("type") == "abort_stream":
                await abort_stream(chat_id, db)
            
    except WebSocketDisconnect:
        stream_manager.disconnect(session_key)
    except Exception as e:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))
        stream_manager.disconnect(session_key)


async def handle_stream_message(
    chat_id: UUID,
    message_data: Dict[str, Any],
    user: User,
    db: AsyncSession,
    websocket: WebSocket
):
    """Handle streaming a message to an LLM provider."""
    
    try:
        # Extract message info
        content = message_data.get("content")
        provider_name = message_data.get("provider")
        model = message_data.get("model")
        parent_message_id = message_data.get("parent_message_id")
        
        if not all([content, provider_name, model]):
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Content, provider, and model are required"
            }))
            return
        
        # Create user message
        user_message = Message(
            chat_session_id=chat_id,
            parent_message_id=parent_message_id,
            role="user",
            content={"text": content},
            is_partial=False
        )
        
        db.add(user_message)
        await db.commit()
        await db.refresh(user_message)
        
        # Get user's API key for the provider
        result = await db.execute(
            select(ProviderKey).where(
                ProviderKey.user_id == user.id,
                ProviderKey.provider_name == provider_name
            )
        )
        provider_key = result.scalar_one_or_none()
        
        if not provider_key:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"No API key found for {provider_name}"
            }))
            return
        
        # Decrypt API key
        api_key = decrypt_api_key(provider_key.encrypted_api_key)
        
        # Build conversation history
        result = await db.execute(
            select(Message)
            .where(Message.chat_session_id == chat_id)
            .order_by(Message.timestamp)
        )
        messages = result.scalars().all()
        
        conversation = []
        for msg in messages:
            if not msg.content.get("deleted", False):
                conversation.append({
                    "role": msg.role,
                    "content": msg.content.get("text", "")
                })
        
        # Stream the response
        await stream_llm_response(
            db=db,
            message_id=user_message.id,
            chat_session_id=chat_id,
            user_id=user.id,
            provider_name=provider_name,
            model=model,
            api_key=api_key,
            messages=conversation,
            websocket=websocket
        )
        
    except Exception as e:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))


@router.post("/{message_id}/abort")
async def abort_message_stream(
    message_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Abort an active stream for a message."""
    
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
            detail="Message not found"
        )
    
    success = await abort_stream(message.chat_session_id, db)
    
    if success:
        return {"message": "Stream aborted successfully"}
    else:
        return {"message": "No active stream to abort"}


@router.post("/{message_id}/continue")
async def continue_message_stream(
    message_id: UUID,
    stream_data: MessageStream,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Continue a previously incomplete stream."""
    
    # Get the message and verify ownership
    result = await db.execute(
        select(Message)
        .join(ChatSession)
        .where(
            Message.id == message_id,
            ChatSession.user_id == current_user.id,
            Message.is_partial == True
        )
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partial message not found"
        )
    
    # Get user's API key
    result = await db.execute(
        select(ProviderKey).where(
            ProviderKey.user_id == current_user.id,
            ProviderKey.provider_name == stream_data.provider
        )
    )
    provider_key = result.scalar_one_or_none()
    
    if not provider_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No API key found for {stream_data.provider}"
        )
    
    # Decrypt API key
    api_key = decrypt_api_key(provider_key.encrypted_api_key)
    
    # Build conversation up to this point
    result = await db.execute(
        select(Message)
        .where(Message.chat_session_id == message.chat_session_id)
        .order_by(Message.timestamp)
    )
    messages = result.scalars().all()
    
    conversation = []
    for msg in messages:
        if msg.id == message_id:
            break
        if not msg.content.get("deleted", False):
            conversation.append({
                "role": msg.role,
                "content": msg.content.get("text", "")
            })
    
    # Continue the stream
    content = await continue_stream(
        db=db,
        message_id=message_id,
        provider_name=stream_data.provider,
        model=stream_data.model,
        api_key=api_key,
        messages=conversation
    )
    
    return {"message": "Stream continued", "content": content} 