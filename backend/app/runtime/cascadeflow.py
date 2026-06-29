"""
CascadeFlow Runtime Intelligence
Automatically selects the best model based on complexity, budget, and policy.
Every routing decision is logged for audit.
"""
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import httpx
import json
import re

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    LOCAL = "local"       # Free, privacy-safe, offline
    FAST = "fast"         # Cheap, low-latency
    BALANCED = "balanced" # Mid-tier reasoning
    POWERFUL = "powerful" # Max capability


@dataclass
class ModelConfig:
    name: str
    tier: ModelTier
    cost_per_1k_tokens: float  # USD
    context_window: int
    provider: str
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    available: bool = True


@dataclass
class RoutingDecision:
    model: ModelConfig
    tier: ModelTier
    complexity_score: float
    routing_reason: str
    budget_remaining_usd: float
    estimated_cost_usd: float
    audit_log: List[str] = field(default_factory=list)


# ── Model registry ──────────────────────────────────────────────────────────

MODELS: Dict[ModelTier, ModelConfig] = {
    ModelTier.LOCAL: ModelConfig(
        name="llama3.2:3b",
        tier=ModelTier.LOCAL,
        cost_per_1k_tokens=0.0,
        context_window=8192,
        provider="ollama",
        base_url=settings.OLLAMA_BASE_URL,
    ),
    ModelTier.FAST: ModelConfig(
        name="llama-3.1-8b-instant",
        tier=ModelTier.FAST,
        cost_per_1k_tokens=0.00005,
        context_window=131072,
        provider="groq",
        api_key_env="GROQ_API_KEY",
    ),
    ModelTier.BALANCED: ModelConfig(
        name="llama-3.3-70b-versatile",
        tier=ModelTier.BALANCED,
        cost_per_1k_tokens=0.00059,
        context_window=131072,
        provider="groq",
        api_key_env="GROQ_API_KEY",
    ),
    ModelTier.POWERFUL: ModelConfig(
        name="gpt-4o",
        tier=ModelTier.POWERFUL,
        cost_per_1k_tokens=0.005,
        context_window=128000,
        provider="openai",
        api_key_env="OPENAI_API_KEY",
    ),
}


class CascadeFlowRuntime:
    """
    Runtime intelligence layer.
    Selects the optimal model automatically, enforces budget, and logs every decision.
    """

    def __init__(self, budget_used_today_usd: float = 0.0):
        self.budget_used = budget_used_today_usd
        self.budget_limit = settings.BUDGET_DAILY_USD

    # ── Complexity analysis ─────────────────────────────────────────────────

    def _analyze_complexity(self, prompt: str, context_size: int) -> Tuple[float, List[str]]:
        """
        Estimate task complexity: 0.0 (trivial) → 1.0 (critical).
        Returns (score, reasoning_steps).
        """
        score = 0.0
        reasons: List[str] = []
        p = prompt.lower()

        # Length signal
        if len(prompt) > 2000:
            score += 0.2
            reasons.append("long prompt (>2000 chars)")
        elif len(prompt) > 500:
            score += 0.1
            reasons.append("medium prompt (>500 chars)")

        # Critical keywords
        critical_kw = ["critical", "outage", "p0", "p1", "production down", "data loss",
                       "security breach", "cascading", "distributed", "memory leak"]
        medium_kw = ["error", "failure", "high", "degraded", "latency", "timeout",
                     "exception", "crash", "alert"]
        simple_kw = ["status", "how to", "what is", "explain", "list", "show"]

        if any(kw in p for kw in critical_kw):
            score += 0.45
            reasons.append("critical production keywords detected")
        elif any(kw in p for kw in medium_kw):
            score += 0.25
            reasons.append("error/failure keywords detected")
        elif any(kw in p for kw in simple_kw):
            reasons.append("informational query")

        # Context richness (memory hits)
        if context_size > 3:
            score += 0.1
            reasons.append("rich memory context (>3 memories)")
        elif context_size > 0:
            score += 0.05
            reasons.append("some memory context available")

        # Multi-service / distributed signals
        if any(kw in p for kw in ["microservice", "kubernetes", "k8s", "distributed", "multi-region"]):
            score += 0.15
            reasons.append("distributed systems context")

        return min(score, 1.0), reasons

    # ── Budget enforcement ──────────────────────────────────────────────────

    def _budget_remaining(self) -> float:
        return max(0.0, self.budget_limit - self.budget_used)

    def _affordable_tier(self, desired: ModelTier, estimated_tokens: int) -> Tuple[ModelTier, str]:
        """Downgrade tier if budget is insufficient."""
        remaining = self._budget_remaining()
        model = MODELS[desired]
        cost = (estimated_tokens / 1000) * model.cost_per_1k_tokens

        if remaining <= 0:
            return ModelTier.LOCAL, "budget exhausted — routing to local model"
        if cost > remaining * 0.5 and desired == ModelTier.POWERFUL:
            return ModelTier.BALANCED, "cost-saving: downgraded from powerful to balanced"
        return desired, ""

    # ── Main routing logic (CascadeFlow) ───────────────────────────────────

    def route(
        self,
        prompt: str,
        memory_context_size: int = 0,
        estimated_tokens: int = 1000,
        force_tier: Optional[ModelTier] = None,
    ) -> RoutingDecision:
        audit: List[str] = []
        audit.append(f"[{datetime.now(timezone.utc).isoformat()}] CascadeFlow routing started")

        complexity, complexity_reasons = self._analyze_complexity(prompt, memory_context_size)
        audit.append(f"Complexity score: {complexity:.2f} — {'; '.join(complexity_reasons)}")

        # Determine ideal tier
        if force_tier:
            ideal_tier = force_tier
            reason = f"tier forced by caller: {force_tier.value}"
        elif complexity <= settings.SIMPLE_COMPLEXITY_THRESHOLD:
            ideal_tier = ModelTier.FAST
            reason = "simple query → fast model"
        elif complexity <= settings.MEDIUM_COMPLEXITY_THRESHOLD:
            ideal_tier = ModelTier.BALANCED
            reason = "medium complexity → balanced model"
        else:
            ideal_tier = ModelTier.POWERFUL
            reason = "high complexity / critical incident → powerful model"

        audit.append(f"Ideal tier: {ideal_tier.value} ({reason})")

        # Budget check — may downgrade
        final_tier, budget_note = self._affordable_tier(ideal_tier, estimated_tokens)
        if budget_note:
            audit.append(f"Budget adjustment: {budget_note}")
            reason = f"{reason} | {budget_note}"

        model = MODELS[final_tier]
        estimated_cost = (estimated_tokens / 1000) * model.cost_per_1k_tokens
        self.budget_used += estimated_cost

        audit.append(f"Selected model: {model.name} (provider: {model.provider})")
        audit.append(f"Estimated cost: ${estimated_cost:.6f} | Budget remaining: ${self._budget_remaining():.4f}")

        decision = RoutingDecision(
            model=model,
            tier=final_tier,
            complexity_score=complexity,
            routing_reason=reason,
            budget_remaining_usd=self._budget_remaining(),
            estimated_cost_usd=estimated_cost,
            audit_log=audit,
        )

        logger.info("🔀 CascadeFlow → %s (complexity=%.2f, cost=$%.6f)", model.name, complexity, estimated_cost)
        return decision

    # ── LLM invocation ─────────────────────────────────────────────────────

    async def invoke(
        self,
        decision: RoutingDecision,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        model = decision.model

        if model.provider == "groq":
            return await self._invoke_groq(model, system_prompt, user_prompt, temperature)
        elif model.provider == "openai":
            return await self._invoke_openai(model, system_prompt, user_prompt, temperature)
        elif model.provider == "ollama":
            return await self._invoke_ollama(model, system_prompt, user_prompt, temperature)
        else:
            raise ValueError(f"Unknown provider: {model.provider}")

    async def _invoke_groq(
        self, model: ModelConfig, system: str, user: str, temp: float
    ) -> Dict[str, Any]:
        api_key = settings.GROQ_API_KEY
        if not api_key:
            # Fallback to demo mode
            return self._demo_response(model, user)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model.name,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temp,
                    "max_tokens": 2000,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "tokens_used": data.get("usage", {}).get("total_tokens", 0),
                "model": model.name,
            }

    async def _invoke_openai(
        self, model: ModelConfig, system: str, user: str, temp: float
    ) -> Dict[str, Any]:
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            return self._demo_response(model, user)
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model.name,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temp,
                    "max_tokens": 3000,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "tokens_used": data.get("usage", {}).get("total_tokens", 0),
                "model": model.name,
            }

    async def _invoke_ollama(
        self, model: ModelConfig, system: str, user: str, temp: float
    ) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{model.base_url}/api/generate",
                    json={
                        "model": model.name,
                        "prompt": f"<|system|>\n{system}\n<|user|>\n{user}\n<|assistant|>",
                        "stream": False,
                        "options": {"temperature": temp},
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "content": data.get("response", ""),
                    "tokens_used": data.get("eval_count", 0),
                    "model": model.name,
                }
        except Exception:
            logger.warning("Ollama unavailable, using demo response")
            return self._demo_response(model, user)

    def _demo_response(self, model: ModelConfig, prompt: str) -> Dict[str, Any]:
        """Fallback demo response when no API keys are configured."""
        p = prompt.lower()
        if "database" in p or "postgres" in p or "db" in p:
            content = (
                "**Root Cause Analysis**: High connection pool exhaustion detected on the PostgreSQL instance.\n\n"
                "**Likely Cause**: Connection pool maxed out due to long-running queries not returning connections. "
                "Possibly caused by a missing index on the `orders` table triggering sequential scans.\n\n"
                "**Recommended Actions**:\n"
                "1. Run `SELECT * FROM pg_stat_activity WHERE state = 'idle in transaction';` to identify stuck connections.\n"
                "2. Increase `max_connections` temporarily: `ALTER SYSTEM SET max_connections = 200;`\n"
                "3. Add missing index: `CREATE INDEX CONCURRENTLY idx_orders_created_at ON orders(created_at);`\n"
                "4. Restart connection pool (PgBouncer if used).\n\n"
                "**Prevention**: Set `idle_in_transaction_session_timeout = '30s'` and add connection pool monitoring."
            )
        elif "memory" in p or "oom" in p or "heap" in p:
            content = (
                "**Root Cause Analysis**: Out-of-memory condition detected.\n\n"
                "**Likely Cause**: Memory leak in the application's object caching layer. "
                "Objects are being retained after request completion due to circular references.\n\n"
                "**Recommended Actions**:\n"
                "1. Restart the affected pod: `kubectl rollout restart deployment/api-service`\n"
                "2. Check heap dumps: enable `--max-old-space-size=512` and capture with `node --inspect`\n"
                "3. Review cache TTL settings — reduce from unlimited to 5 minutes.\n\n"
                "**Prevention**: Add Prometheus memory alerts at 80% threshold and weekly heap profiling."
            )
        else:
            content = (
                "**Incident Analysis**:\n\n"
                "Based on the reported symptoms, this appears to be a service degradation event.\n\n"
                "**Immediate Actions**:\n"
                "1. Check service health: `kubectl get pods -n production`\n"
                "2. Review recent deployments: `kubectl rollout history deployment`\n"
                "3. Check logs: `kubectl logs -l app=api-service --tail=100`\n"
                "4. Verify upstream dependencies are healthy.\n\n"
                "**Escalation**: If symptoms persist beyond 15 minutes, escalate to on-call engineer."
            )
        return {"content": content, "tokens_used": 350, "model": f"{model.name} (demo)"}
