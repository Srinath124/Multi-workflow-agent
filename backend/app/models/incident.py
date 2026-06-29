"""
ORM models — Incidents
"""
from sqlalchemy import Column, String, Text, DateTime, Enum, Float, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from datetime import datetime, timezone
import uuid
import enum


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(Enum(Severity), nullable=False, default=Severity.MEDIUM)
    status = Column(Enum(IncidentStatus), nullable=False, default=IncidentStatus.OPEN)
    service = Column(String(200), nullable=True)
    environment = Column(String(100), nullable=True, default="production")

    # AI-generated fields
    root_cause = Column(Text, nullable=True)
    resolution = Column(Text, nullable=True)
    ai_analysis = Column(Text, nullable=True)
    model_used = Column(String(100), nullable=True)
    routing_reason = Column(String(500), nullable=True)
    complexity_score = Column(Float, nullable=True)
    cost_usd = Column(Float, nullable=True, default=0.0)

    # Memory-related
    similar_incident_ids = Column(JSON, nullable=True, default=list)
    memory_ids = Column(JSON, nullable=True, default=list)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)
