"""
Incidents API — CRUD + AI analysis endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
import uuid

from app.core.database import get_db
from app.core.agent import IncidentResponseAgent
from app.models.incident import Incident, Severity, IncidentStatus

router = APIRouter()


# ── Pydantic schemas ────────────────────────────────────────────────────────

class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=500)
    description: str = Field(..., min_length=10)
    severity: Severity = Severity.MEDIUM
    service: Optional[str] = None
    environment: str = "production"


class IncidentResolve(BaseModel):
    resolution_notes: str = Field(..., min_length=10)
    root_cause: str = Field(..., min_length=10)
    lessons: Optional[List[str]] = None


class IncidentResponse(BaseModel):
    id: str
    title: str
    description: str
    severity: str
    status: str
    service: Optional[str]
    environment: str
    ai_analysis: Optional[str]
    root_cause: Optional[str]
    resolution: Optional[str]
    model_used: Optional[str]
    routing_reason: Optional[str]
    complexity_score: Optional[float]
    cost_usd: Optional[float]
    memory_hits: Optional[int]
    created_at: str
    updated_at: str
    resolved_at: Optional[str]


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/incidents", status_code=201)
async def create_and_analyze_incident(
    payload: IncidentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new incident and trigger AI analysis immediately."""
    # Persist the incident first
    incident = Incident(
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        service=payload.service,
        environment=payload.environment,
        status=IncidentStatus.INVESTIGATING,
    )
    db.add(incident)
    await db.flush()
    incident_id = str(incident.id)

    # Run AI analysis
    agent = IncidentResponseAgent(db)
    try:
        result = await agent.process_incident(
            title=payload.title,
            description=payload.description,
            severity=payload.severity.value,
            service=payload.service or "unknown",
            environment=payload.environment,
            incident_id=incident_id,
        )

        # Persist AI results back to incident
        incident.ai_analysis = result["analysis"]
        incident.root_cause = result["root_cause"]
        incident.model_used = result["model_used"]
        incident.routing_reason = result["routing_reason"]
        incident.complexity_score = result["complexity_score"]
        incident.cost_usd = result["cost_usd"]
        incident.similar_incident_ids = [
            m.get("source_incident_id") for m in result["similar_memories"]
            if m.get("source_incident_id")
        ]
        await db.flush()

    except Exception as exc:
        incident.ai_analysis = f"Analysis failed: {str(exc)}"
        await db.flush()
        result = {"analysis": incident.ai_analysis, "error": str(exc)}

    return {
        "incident_id": incident_id,
        "status": "investigating",
        "ai_result": result,
    }


@router.get("/incidents", response_model=List[IncidentResponse])
async def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List all incidents with optional filters."""
    stmt = select(Incident).order_by(Incident.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Incident.status == status)
    if severity:
        stmt = stmt.where(Incident.severity == severity)
    incidents = (await db.execute(stmt)).scalars().all()
    return [_to_response(i) for i in incidents]


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single incident by ID."""
    incident = await _get_or_404(db, incident_id)
    return _to_response(incident)


@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    payload: IncidentResolve,
    db: AsyncSession = Depends(get_db),
):
    """Resolve an incident and commit knowledge to long-term memory."""
    await _get_or_404(db, incident_id)
    agent = IncidentResponseAgent(db)
    result = await agent.resolve_incident(
        incident_id=incident_id,
        resolution_notes=payload.resolution_notes,
        root_cause=payload.root_cause,
        lessons=payload.lessons,
    )
    return result


@router.get("/incidents/stats/summary")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Dashboard summary statistics."""
    total = (await db.execute(select(func.count(Incident.id)))).scalar()
    resolved = (await db.execute(
        select(func.count(Incident.id)).where(Incident.status == IncidentStatus.RESOLVED)
    )).scalar()
    critical = (await db.execute(
        select(func.count(Incident.id)).where(Incident.severity == Severity.CRITICAL)
    )).scalar()
    total_cost = (await db.execute(select(func.sum(Incident.cost_usd)))).scalar() or 0.0

    return {
        "total_incidents": total,
        "resolved": resolved,
        "open": total - resolved,
        "critical": critical,
        "total_ai_cost_usd": round(total_cost, 6),
    }


# ── Helpers ─────────────────────────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, incident_id: str) -> Incident:
    try:
        uid = uuid.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    result = await db.execute(select(Incident).where(Incident.id == uid))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


def _to_response(i: Incident) -> IncidentResponse:
    return IncidentResponse(
        id=str(i.id),
        title=i.title,
        description=i.description,
        severity=i.severity.value,
        status=i.status.value,
        service=i.service,
        environment=i.environment,
        ai_analysis=i.ai_analysis,
        root_cause=i.root_cause,
        resolution=i.resolution,
        model_used=i.model_used,
        routing_reason=i.routing_reason,
        complexity_score=i.complexity_score,
        cost_usd=i.cost_usd,
        memory_hits=len(i.memory_ids or []),
        created_at=i.created_at.isoformat(),
        updated_at=i.updated_at.isoformat(),
        resolved_at=i.resolved_at.isoformat() if i.resolved_at else None,
    )
