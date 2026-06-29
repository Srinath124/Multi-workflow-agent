"""
AI Incident Response Engineer — Main FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.api import incidents, memory, health, chat
from app.core.config import settings
from app.core.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Incident Response Agent...")
    await init_db()
    logger.info("✅ Database initialized")
    yield
    logger.info("🛑 Shutting down Incident Response Agent")


app = FastAPI(
    title="AI Incident Response Engineer",
    description="Production-ready AI agent with persistent memory and intelligent runtime decision-making",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(incidents.router, prefix="/api/v1", tags=["incidents"])
app.include_router(memory.router, prefix="/api/v1", tags=["memory"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])


@app.get("/")
async def root():
    return {
        "service": "AI Incident Response Engineer",
        "version": "1.0.0",
        "status": "operational",
    }
