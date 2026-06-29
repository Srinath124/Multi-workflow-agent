"""
Hindsight Memory Service
Persistent long-term memory: store, retrieve, and reflect on organizational knowledge.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from datetime import datetime, timezone
import numpy as np
import json
import logging
import uuid

from app.models.memory_record import MemoryRecord, MemoryCategory
from app.core.config import settings

logger = logging.getLogger(__name__)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    a_np = np.array(a, dtype=np.float32)
    b_np = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(a_np)
    norm_b = np.linalg.norm(b_np)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_np, b_np) / (norm_a * norm_b))


def _simple_embedding(text: str) -> List[float]:
    """
    Lightweight deterministic embedding for demo / offline use.
    In production, replace with OpenAI text-embedding-3-small or similar.
    """
    words = text.lower().split()
    vocab: Dict[str, int] = {}
    for w in words:
        vocab[w] = vocab.get(w, 0) + 1
    # Fixed 128-dim hash-space vector
    dim = 128
    vec = [0.0] * dim
    for word, count in vocab.items():
        idx = hash(word) % dim
        vec[idx] += count
    total = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / total for v in vec]


class HindsightMemoryService:
    """
    Hindsight-inspired persistent memory layer.
    Stores organizational knowledge and retrieves semantically similar memories.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Write ──────────────────────────────────────────────────────────────

    async def store(
        self,
        category: MemoryCategory,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        source_incident_id: Optional[str] = None,
        confidence_score: float = 1.0,
    ) -> MemoryRecord:
        embedding = _simple_embedding(f"{title} {content}")
        record = MemoryRecord(
            category=category,
            title=title,
            content=content,
            tags=tags or [],
            source_incident_id=uuid.UUID(source_incident_id) if source_incident_id else None,
            embedding=embedding,
            embedding_model="simple-hash-128",
            confidence_score=confidence_score,
        )
        self.db.add(record)
        await self.db.flush()
        logger.info("📝 Memory stored: [%s] %s", category.value, title)
        return record

    # ── Read ───────────────────────────────────────────────────────────────

    async def retrieve(
        self,
        query: str,
        category: Optional[MemoryCategory] = None,
        top_k: int = None,
        threshold: float = None,
    ) -> List[Dict[str, Any]]:
        top_k = top_k or settings.MEMORY_MAX_RESULTS
        threshold = threshold or settings.MEMORY_SIMILARITY_THRESHOLD

        query_embedding = _simple_embedding(query)

        stmt = select(MemoryRecord)
        if category:
            stmt = stmt.where(MemoryRecord.category == category)
        records = (await self.db.execute(stmt)).scalars().all()

        scored: List[tuple[float, MemoryRecord]] = []
        for rec in records:
            if rec.embedding:
                score = _cosine_similarity(query_embedding, rec.embedding)
                if score >= threshold:
                    scored.append((score, rec))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, rec in scored[:top_k]:
            # Update retrieval stats async
            rec.retrieval_count = (rec.retrieval_count or 0) + 1
            rec.last_retrieved_at = datetime.now(timezone.utc)
            results.append({
                "id": str(rec.id),
                "category": rec.category.value,
                "title": rec.title,
                "content": rec.content,
                "tags": rec.tags or [],
                "similarity_score": round(score, 4),
                "confidence_score": rec.confidence_score,
                "source_incident_id": str(rec.source_incident_id) if rec.source_incident_id else None,
                "created_at": rec.created_at.isoformat(),
            })

        await self.db.flush()
        logger.info("🔍 Memory retrieved %d results for query: '%s…'", len(results), query[:60])
        return results

    async def reflect_and_store(
        self,
        incident_id: str,
        incident_title: str,
        root_cause: str,
        resolution: str,
        service: str,
        severity: str,
        lessons: Optional[List[str]] = None,
    ) -> List[MemoryRecord]:
        """
        Post-incident reflection — store structured knowledge for future retrieval.
        """
        stored = []

        # 1. Incident record
        rec = await self.store(
            MemoryCategory.INCIDENT,
            f"Incident: {incident_title}",
            f"Service: {service} | Severity: {severity} | {incident_title}",
            tags=[service, severity, "incident"],
            source_incident_id=incident_id,
        )
        stored.append(rec)

        # 2. Root cause
        if root_cause:
            rec = await self.store(
                MemoryCategory.ROOT_CAUSE,
                f"Root cause for {incident_title}",
                root_cause,
                tags=[service, "root-cause"],
                source_incident_id=incident_id,
            )
            stored.append(rec)

        # 3. Resolution
        if resolution:
            rec = await self.store(
                MemoryCategory.RESOLUTION,
                f"Resolution for {incident_title}",
                resolution,
                tags=[service, "resolution", "fix"],
                source_incident_id=incident_id,
            )
            stored.append(rec)

        # 4. Lessons learned
        for lesson in (lessons or []):
            rec = await self.store(
                MemoryCategory.REFLECTION,
                f"Lesson from {incident_title}",
                lesson,
                tags=[service, "lesson", "reflection"],
                source_incident_id=incident_id,
            )
            stored.append(rec)

        logger.info("🧠 Reflection complete — stored %d memory records", len(stored))
        return stored

    async def get_all(
        self,
        category: Optional[MemoryCategory] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        stmt = select(MemoryRecord).order_by(MemoryRecord.created_at.desc()).limit(limit)
        if category:
            stmt = stmt.where(MemoryRecord.category == category)
        records = (await self.db.execute(stmt)).scalars().all()
        return [
            {
                "id": str(r.id),
                "category": r.category.value,
                "title": r.title,
                "content": r.content,
                "tags": r.tags or [],
                "retrieval_count": r.retrieval_count or 0,
                "confidence_score": r.confidence_score,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]
