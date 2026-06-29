"""
Chat API — Conversation CRUD + multi-turn chat endpoint
Inspired by Nasiko's Chat History Service + OpenAI's conversation model.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import logging

from app.core.database import get_db
from app.core.agent import IncidentResponseAgent
from app.models.conversation import Conversation, ChatMessage, MessageRole
from app.memory.learning import (
    ConversationLearningEngine,
    QualityValidator,
    ModelSuccessTracker,
    detect_domain,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic Schemas ──────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None


class ConversationRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    model_used: Optional[str] = None
    model_tier: Optional[str] = None
    complexity_score: Optional[float] = None
    cost_usd: Optional[float] = None
    tokens_used: Optional[int] = None
    routing_reason: Optional[str] = None
    memory_hits: Optional[int] = None
    high_confidence_hits: Optional[int] = None
    pipeline_log: Optional[List[str]] = None
    cascade_audit: Optional[List[str]] = None
    quality_passed: Optional[bool] = None
    confidence_score: Optional[float] = None
    domain_detected: Optional[str] = None
    created_at: str


class ConversationResponse(BaseModel):
    id: str
    title: str
    message_count: int
    total_cost_usd: float
    model_tiers_used: Optional[List[str]] = None
    domain_tags: Optional[List[str]] = None
    created_at: str
    updated_at: str


class ConversationDetailResponse(ConversationResponse):
    messages: List[ChatMessageResponse]


# ── Auto-Title Generation ─────────────────────────────────────────────────

def _generate_title(message: str) -> str:
    """Generate a conversation title from the first message."""
    clean = message.strip()
    if len(clean) <= 60:
        return clean
    # Find the last word boundary before 60 chars
    truncated = clean[:60]
    last_space = truncated.rfind(" ")
    if last_space > 20:
        return truncated[:last_space] + "..."
    return truncated + "..."


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/chat")
async def send_chat_message(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message in a conversation.
    If no conversation_id is provided, creates a new conversation.
    Returns the assistant's response with full pipeline metadata.
    """
    conversation = None

    # Get or create conversation
    if payload.conversation_id:
        try:
            conv_uuid = uuid.UUID(payload.conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation ID")
        result = await db.execute(
            select(Conversation).where(Conversation.id == conv_uuid)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        # Create new conversation
        conversation = Conversation(
            title=_generate_title(payload.message),
        )
        db.add(conversation)
        await db.flush()

    conv_id = conversation.id

    # Store user message
    user_msg = ChatMessage(
        conversation_id=conv_id,
        role=MessageRole.USER,
        content=payload.message,
    )
    db.add(user_msg)
    await db.flush()

    # Get conversation history for context
    learning_engine = ConversationLearningEngine(db)
    history = await learning_engine.get_conversation_context(str(conv_id), last_n=10)

    # Process with the agent
    agent = IncidentResponseAgent(db)
    try:
        result = await agent.process_chat_message(
            message=payload.message,
            conversation_history=history,
        )

        # Detect domain & validate quality
        domain = detect_domain(payload.message)
        quality = QualityValidator.validate(result["analysis"], payload.message)

        # Track model success for self-improvement
        ModelSuccessTracker.record_outcome(
            domain=domain,
            model_tier=result.get("model_tier", "unknown"),
            quality_score=quality["confidence"],
        )

        # Store assistant message
        assistant_msg = ChatMessage(
            conversation_id=conv_id,
            role=MessageRole.ASSISTANT,
            content=result["analysis"],
            model_used=result.get("model_used"),
            model_tier=result.get("model_tier"),
            complexity_score=result.get("complexity_score"),
            cost_usd=result.get("cost_usd", 0.0),
            tokens_used=result.get("tokens_used", 0),
            routing_reason=result.get("routing_reason"),
            memory_hits=result.get("memory_hits", 0),
            high_confidence_hits=result.get("high_confidence_hits", 0),
            pipeline_log=result.get("pipeline_log", []),
            cascade_audit=result.get("cascade_audit", []),
            quality_passed=quality["passed"],
            confidence_score=quality["confidence"],
            domain_detected=domain,
        )
        db.add(assistant_msg)

        # Update conversation stats
        conversation.message_count = (conversation.message_count or 0) + 2
        conversation.total_cost_usd = (conversation.total_cost_usd or 0) + (result.get("cost_usd", 0.0))
        conversation.total_tokens = (conversation.total_tokens or 0) + (result.get("tokens_used", 0))
        tiers = conversation.model_tiers_used or []
        tier_val = result.get("model_tier", "unknown")
        if tier_val not in tiers:
            tiers.append(tier_val)
        conversation.model_tiers_used = tiers
        conversation.updated_at = datetime.now(timezone.utc)

        await db.flush()

        return {
            "conversation_id": str(conv_id),
            "user_message": {
                "id": str(user_msg.id),
                "role": "user",
                "content": payload.message,
                "created_at": user_msg.created_at.isoformat(),
            },
            "assistant_message": {
                "id": str(assistant_msg.id),
                "role": "assistant",
                "content": result["analysis"],
                "model_used": result.get("model_used"),
                "model_tier": result.get("model_tier"),
                "complexity_score": result.get("complexity_score"),
                "cost_usd": result.get("cost_usd", 0.0),
                "tokens_used": result.get("tokens_used", 0),
                "routing_reason": result.get("routing_reason"),
                "memory_hits": result.get("memory_hits", 0),
                "high_confidence_hits": result.get("high_confidence_hits", 0),
                "pipeline_log": result.get("pipeline_log", []),
                "cascade_audit": result.get("cascade_audit", []),
                "quality_passed": quality["passed"],
                "confidence_score": quality["confidence"],
                "domain_detected": domain,
                "created_at": assistant_msg.created_at.isoformat(),
            },
        }

    except Exception as exc:
        logger.error("Chat processing failed: %s", str(exc))
        # Store error response
        error_msg = ChatMessage(
            conversation_id=conv_id,
            role=MessageRole.ASSISTANT,
            content=f"I encountered an error processing your request: {str(exc)}. Please try again.",
        )
        db.add(error_msg)
        conversation.message_count = (conversation.message_count or 0) + 2
        await db.flush()

        return {
            "conversation_id": str(conv_id),
            "user_message": {
                "id": str(user_msg.id),
                "role": "user",
                "content": payload.message,
                "created_at": user_msg.created_at.isoformat(),
            },
            "assistant_message": {
                "id": str(error_msg.id),
                "role": "assistant",
                "content": error_msg.content,
                "created_at": error_msg.created_at.isoformat(),
            },
            "error": str(exc),
        }


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List all conversations ordered by most recent."""
    stmt = (
        select(Conversation)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    conversations = result.scalars().all()
    return [
        ConversationResponse(
            id=str(c.id),
            title=c.title,
            message_count=c.message_count or 0,
            total_cost_usd=c.total_cost_usd or 0.0,
            model_tiers_used=c.model_tiers_used,
            domain_tags=c.domain_tags,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a full conversation with all messages."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_uuid)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = [
        ChatMessageResponse(
            id=str(m.id),
            role=m.role.value,
            content=m.content,
            model_used=m.model_used,
            model_tier=m.model_tier,
            complexity_score=m.complexity_score,
            cost_usd=m.cost_usd,
            tokens_used=m.tokens_used,
            routing_reason=m.routing_reason,
            memory_hits=m.memory_hits,
            high_confidence_hits=m.high_confidence_hits,
            pipeline_log=m.pipeline_log,
            cascade_audit=m.cascade_audit,
            quality_passed=m.quality_passed,
            confidence_score=m.confidence_score,
            domain_detected=m.domain_detected,
            created_at=m.created_at.isoformat(),
        )
        for m in (conversation.messages or [])
    ]

    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "message_count": conversation.message_count or 0,
        "total_cost_usd": conversation.total_cost_usd or 0.0,
        "model_tiers_used": conversation.model_tiers_used,
        "domain_tags": conversation.domain_tags,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
        "messages": [m.model_dump() for m in messages],
    }


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    payload: ConversationRename,
    db: AsyncSession = Depends(get_db),
):
    """Rename a conversation."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_uuid)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.title = payload.title
    conversation.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return {"id": str(conversation.id), "title": conversation.title}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_uuid)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conversation)
    await db.flush()

    return {"deleted": True, "conversation_id": conversation_id}


@router.post("/conversations/{conversation_id}/learn")
async def learn_from_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Trigger learning engine to extract knowledge from a conversation."""
    engine = ConversationLearningEngine(db)
    result = await engine.learn_from_conversation(conversation_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/learning/stats")
async def get_learning_stats():
    """Get model success tracking statistics (self-improving routing data)."""
    return {
        "model_stats": ModelSuccessTracker.get_stats(),
        "description": "Tracks which model tiers produce the best quality results per domain",
    }
