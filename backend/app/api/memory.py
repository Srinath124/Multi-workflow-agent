"""
Memory API — Hindsight memory management endpoints
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, List

from app.core.database import get_db
from app.memory.hindsight import HindsightMemoryService
from app.models.memory_record import MemoryCategory

router = APIRouter()


class MemoryStoreRequest(BaseModel):
    category: MemoryCategory
    title: str = Field(..., min_length=3)
    content: str = Field(..., min_length=10)
    tags: Optional[List[str]] = None


class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=3)
    category: Optional[MemoryCategory] = None
    top_k: int = Field(default=5, ge=1, le=20)


@router.post("/memory/store", status_code=201)
async def store_memory(payload: MemoryStoreRequest, db: AsyncSession = Depends(get_db)):
    """Manually store a knowledge entry in long-term memory."""
    svc = HindsightMemoryService(db)
    record = await svc.store(
        category=payload.category,
        title=payload.title,
        content=payload.content,
        tags=payload.tags,
    )
    return {"id": str(record.id), "category": record.category.value, "title": record.title}


@router.post("/memory/search")
async def search_memory(payload: MemorySearchRequest, db: AsyncSession = Depends(get_db)):
    """Semantic search across all stored memories."""
    svc = HindsightMemoryService(db)
    results = await svc.retrieve(
        query=payload.query,
        category=payload.category,
        top_k=payload.top_k,
    )
    return {"query": payload.query, "results": results, "count": len(results)}


@router.get("/memory")
async def list_memory(
    category: Optional[str] = None,
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all memory records."""
    svc = HindsightMemoryService(db)
    cat = MemoryCategory(category) if category else None
    records = await svc.get_all(category=cat, limit=limit)
    return {"records": records, "count": len(records)}
