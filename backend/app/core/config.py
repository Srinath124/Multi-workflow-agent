"""
Core configuration — reads from environment variables
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    SECRET_KEY: str = "changeme-in-production"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/incident_agent"
    REDIS_URL: str = "redis://redis:6379/0"

    # AI / LLM
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://ollama:11434"

    # Memory (Hindsight-compatible vector store)
    MEMORY_SIMILARITY_THRESHOLD: float = 0.75
    MEMORY_MAX_RESULTS: int = 5

    # Runtime intelligence thresholds
    BUDGET_DAILY_USD: float = 10.0
    SIMPLE_COMPLEXITY_THRESHOLD: float = 0.3
    MEDIUM_COMPLEXITY_THRESHOLD: float = 0.65

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://frontend:3000"]

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
