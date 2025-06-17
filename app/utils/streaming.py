import asyncio
import json
from typing import Dict, Any, Optional, Set
from uuid import UUID
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Message, ChatSession
from app.db.schemas import StreamResponse, StreamToken
from app.services.provider_clients import get_provider
from app.core.security import decrypt_api_key


class StreamManager:
    """Manages active streaming connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.streaming_sessions: Set[str] = set()
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept a WebSocket connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
    
    def disconnect(self, session_id: str):
        """Remove a WebSocket connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        self.streaming_sessions.discard(session_id)
    
    async def send_message(self, session_id: str, message: Dict[str, Any]):
        """Send a message to a specific WebSocket."""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_text(json.dumps(message))
            except:
                self.disconnect(session_id)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected WebSockets."""
        for session_id in list(self.active_connections.keys()):
            await self.send_message(session_id, message)
    
    def is_streaming(self, session_id: str) -> bool:
        """Check if a session is currently streaming."""
        return session_id in self.streaming_sessions
    
    def start_streaming(self, session_id: str):
        """Mark a session as streaming."""
        self.streaming_sessions.add(session_id)
    
    def stop_streaming(self, session_id: str):
        """Mark a session as not streaming."""
        self.streaming_sessions.discard(session_id)


# Global stream manager instance
stream_manager = StreamManager()


async def stream_llm_response(
    db: AsyncSession,
    message_id: UUID,
    chat_session_id: UUID,
    user_id: UUID,
    provider_name: str,
    model: str,
    api_key: str,
    messages: list[Dict[str, str]],
    websocket: Optional[WebSocket] = None
) -> str:
    """Stream LLM response and save to database."""
    
    # Get the provider client
    provider = get_provider(provider_name, api_key)
    
    # Create the assistant message in database
    assistant_message = Message(
        chat_session_id=chat_session_id,
        parent_message_id=message_id,
        role="assistant",
        content={"text": ""},
        is_partial=True,
        model=model,
        provider=provider_name
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)
    
    content = ""
    session_key = str(chat_session_id)
    
    try:
        # Mark session as streaming
        stream_manager.start_streaming(session_key)
        
        # Send initial response
        if websocket:
            await websocket.send_text(json.dumps({
                "type": "stream_start",
                "message_id": str(assistant_message.id),
                "status": "streaming"
            }))
        
        # Stream tokens from the provider
        async for token in provider.stream_chat(messages, model):
            content += token
            
            # Update message in database periodically
            assistant_message.content = {"text": content}
            await db.commit()
            
            # Send token to WebSocket
            if websocket:
                await websocket.send_text(json.dumps({
                    "type": "token",
                    "message_id": str(assistant_message.id),
                    "token": token,
                    "content": content
                }))
        
        # Mark message as complete
        assistant_message.is_partial = False
        assistant_message.content = {"text": content}
        await db.commit()
        
        # Send completion message
        if websocket:
            await websocket.send_text(json.dumps({
                "type": "stream_complete",
                "message_id": str(assistant_message.id),
                "status": "complete",
                "content": content
            }))
        
    except Exception as e:
        # Mark message as error
        assistant_message.content = {"text": content, "error": str(e)}
        assistant_message.is_partial = False
        await db.commit()
        
        # Send error message
        if websocket:
            await websocket.send_text(json.dumps({
                "type": "stream_error",
                "message_id": str(assistant_message.id),
                "status": "error",
                "error": str(e),
                "content": content
            }))
        
        raise e
    
    finally:
        # Clean up
        stream_manager.stop_streaming(session_key)
        await provider.close()
    
    return content


async def abort_stream(chat_session_id: UUID, db: AsyncSession):
    """Abort an active stream."""
    session_key = str(chat_session_id)
    
    if stream_manager.is_streaming(session_key):
        stream_manager.stop_streaming(session_key)
        
        # Send abort message to WebSocket
        await stream_manager.send_message(session_key, {
            "type": "stream_aborted",
            "status": "aborted"
        })
        
        return True
    
    return False


async def continue_stream(
    db: AsyncSession,
    message_id: UUID,
    provider_name: str,
    model: str,
    api_key: str,
    messages: list[Dict[str, str]],
    websocket: Optional[WebSocket] = None
) -> str:
    """Continue a previously incomplete stream."""
    
    # Get the message
    result = await db.execute(
        select(Message).where(Message.id == message_id)
    )
    message = result.scalar_one_or_none()
    
    if not message or not message.is_partial:
        raise ValueError("Message not found or not partial")
    
    # Get existing content
    existing_content = message.content.get("text", "") if message.content else ""
    
    # Continue streaming from where we left off
    provider = get_provider(provider_name, api_key)
    session_key = str(message.chat_session_id)
    
    try:
        stream_manager.start_streaming(session_key)
        
        # Send continue message
        if websocket:
            await websocket.send_text(json.dumps({
                "type": "stream_continue",
                "message_id": str(message_id),
                "status": "streaming",
                "existing_content": existing_content
            }))
        
        # Stream additional tokens
        content = existing_content
        async for token in provider.stream_chat(messages, model):
            content += token
            
            # Update message
            message.content = {"text": content}
            await db.commit()
            
            # Send token
            if websocket:
                await websocket.send_text(json.dumps({
                    "type": "token",
                    "message_id": str(message_id),
                    "token": token,
                    "content": content
                }))
        
        # Mark as complete
        message.is_partial = False
        await db.commit()
        
        if websocket:
            await websocket.send_text(json.dumps({
                "type": "stream_complete",
                "message_id": str(message_id),
                "status": "complete",
                "content": content
            }))
        
    except Exception as e:
        message.content = {"text": content, "error": str(e)}
        message.is_partial = False
        await db.commit()
        
        if websocket:
            await websocket.send_text(json.dumps({
                "type": "stream_error",
                "message_id": str(message_id),
                "status": "error",
                "error": str(e)
            }))
        
        raise e
    
    finally:
        stream_manager.stop_streaming(session_key)
        await provider.close()
    
    return content 