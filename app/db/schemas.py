from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr
from uuid import UUID


# Base schemas
class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: Optional[str] = None
    sso_id: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class User(UserBase):
    id: UUID
    sso_id: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Provider Key schemas
class ProviderKeyBase(BaseModel):
    provider_name: str


class ProviderKeyCreate(ProviderKeyBase):
    api_key: str  # Plain text, will be encrypted before storage


class ProviderKey(ProviderKeyBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


# Chat Session schemas
class ChatSessionBase(BaseModel):
    name: Optional[str] = None


class ChatSessionCreate(ChatSessionBase):
    pass


class ChatSession(ChatSessionBase):
    id: UUID
    user_id: UUID
    root_message_id: Optional[UUID]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatSessionWithMessages(ChatSession):
    messages: List["Message"] = []


# Message schemas
class MessageBase(BaseModel):
    role: str  # user, assistant, system
    content: Any  # Can be string or complex object


class MessageCreate(MessageBase):
    parent_message_id: Optional[UUID] = None


class MessageStream(BaseModel):
    model: str
    provider: str
    parent_message_id: Optional[UUID] = None


class Message(MessageBase):
    id: UUID
    chat_session_id: UUID
    parent_message_id: Optional[UUID]
    timestamp: datetime
    is_partial: bool
    model: Optional[str]
    provider: Optional[str]
    
    class Config:
        from_attributes = True


# Branch schemas
class BranchCreate(BaseModel):
    base_message_id: UUID


class Branch(BaseModel):
    id: UUID
    base_message_id: UUID
    new_session_id: UUID
    created_by: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True


# Auth schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# System schemas
class ProviderInfo(BaseModel):
    name: str
    models: List[str]
    description: str


class ModelInfo(BaseModel):
    name: str
    provider: str
    description: str
    max_tokens: int


# Stream schemas
class StreamToken(BaseModel):
    token: str
    is_complete: bool = False


class StreamResponse(BaseModel):
    message_id: UUID
    status: str  # streaming, complete, error, aborted
    content: str = "" 