"""
ORM models — Conversations & Chat Messages
Persistent multi-turn chat with full audit trail per message.
"""
from sqlalchemy import Column, String, Text, DateTime, Float, JSON, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime, timezone
import uuid
import enum


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False, default="New Conversation")
    summary = Column(Text, nullable=True)

    # Aggregated stats
    message_count = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)
    total_tokens = Column(Integer, default=0)
    model_tiers_used = Column(JSON, nullable=True, default=list)

    # Learning metadata
    learning_extracted = Column(JSON, nullable=True, default=False)
    domain_tags = Column(JSON, nullable=True, default=list)
    quality_score = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    messages = relationship("ChatMessage", back_populates="conversation", order_by="ChatMessage.created_at",
                            cascade="all, delete-orphan", lazy="selectin")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(SAEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)

    # AI metadata (only for assistant messages)
    model_used = Column(String(100), nullable=True)
    model_tier = Column(String(50), nullable=True)
    complexity_score = Column(Float, nullable=True)
    cost_usd = Column(Float, nullable=True, default=0.0)
    tokens_used = Column(Integer, nullable=True, default=0)
    routing_reason = Column(String(500), nullable=True)

    # Memory & learning
    memory_hits = Column(Integer, nullable=True, default=0)
    high_confidence_hits = Column(Integer, nullable=True, default=0)
    pipeline_log = Column(JSON, nullable=True, default=list)
    cascade_audit = Column(JSON, nullable=True, default=list)

    # Quality validation (from CascadeFlow strategy)
    quality_passed = Column(JSON, nullable=True, default=True)
    confidence_score = Column(Float, nullable=True)
    domain_detected = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="messages")
