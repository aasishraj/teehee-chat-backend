from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from .database import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    sso_id = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    provider_keys = relationship("ProviderKey", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    created_branches = relationship("Branch", back_populates="created_by_user")


class ProviderKey(Base):
    __tablename__ = "provider_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider_name = Column(String, nullable=False)  # openai, anthropic, mistral, etc.
    encrypted_api_key = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="provider_keys")


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    root_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    name = Column(String, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("Message", back_populates="chat_session", cascade="all, delete-orphan")
    branches = relationship("Branch", back_populates="new_session")


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    parent_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)
    role = Column(String, nullable=False)  # user, assistant, system
    content = Column(JSON, nullable=False)  # Can store text or complex content
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    is_partial = Column(Boolean, default=False)
    model = Column(String, nullable=True)  # Model used for assistant messages
    provider = Column(String, nullable=True)  # Provider used for assistant messages
    
    # Relationships
    chat_session = relationship("ChatSession", back_populates="messages")
    parent = relationship("Message", remote_side=[id])
    children = relationship("Message", back_populates="parent")
    base_branches = relationship("Branch", back_populates="base_message")


class Branch(Base):
    __tablename__ = "branches"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    base_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False)
    new_session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    base_message = relationship("Message", back_populates="base_branches")
    new_session = relationship("ChatSession", back_populates="branches")
    created_by_user = relationship("User", back_populates="created_branches") 