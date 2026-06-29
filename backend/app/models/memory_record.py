"""
ORM models — Memory Records (Hindsight-compatible)
"""
from sqlalchemy import Column, String, Text, DateTime, Enum, JSON, Float, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.core.database import Base
from datetime import datetime, timezone
import uuid
import enum


class MemoryCategory(str, enum.Enum):
    INCIDENT = "incident"
    ROOT_CAUSE = "root_cause"
    RESOLUTION = "resolution"
    INFRASTRUCTURE = "infrastructure"
    PREFERENCE = "preference"
    POLICY = "policy"
    REFLECTION = "reflection"
    WORKFLOW = "workflow"


class MemoryRecord(Base):
    __tablename__ = "memory_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(Enum(MemoryCategory), nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(JSON, nullable=True, default=list)
    source_incident_id = Column(UUID(as_uuid=True), nullable=True)

    # Vector embedding (stored as JSON array for portability; swap for pgvector in prod)
    embedding = Column(JSON, nullable=True)
    embedding_model = Column(String(100), nullable=True)

    # Retrieval metadata
    retrieval_count = Column(Float, nullable=True, default=0)
    last_retrieved_at = Column(DateTime(timezone=True), nullable=True)
    confidence_score = Column(Float, nullable=True, default=1.0)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_memory_category", "category"),
        Index("ix_memory_source_incident", "source_incident_id"),
    )
