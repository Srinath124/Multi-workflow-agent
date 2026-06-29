"""
Conversation Learning Engine
Inspired by Vectorize Self-Driving Agents + Hindsight:
  - Extracts knowledge patterns from past conversations
  - Tracks model success rates per domain for self-improving routing
  - Builds conversation-derived memory for future context enrichment
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone
import logging

from app.models.conversation import Conversation, ChatMessage, MessageRole
from app.models.memory_record import MemoryCategory
from app.memory.hindsight import HindsightMemoryService

logger = logging.getLogger(__name__)


# ── Domain Detection (from CascadeFlow strategy) ──────────────────────────

DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "DATABASE": ["postgres", "mysql", "redis", "mongo", "database", "sql", "query", "index",
                 "connection pool", "replication", "deadlock", "schema"],
    "KUBERNETES": ["kubernetes", "k8s", "pod", "deployment", "service mesh", "helm",
                   "kubectl", "namespace", "ingress", "container", "docker"],
    "NETWORK": ["dns", "load balancer", "proxy", "nginx", "ssl", "tls", "tcp",
                "udp", "firewall", "vpn", "latency", "bandwidth"],
    "SECURITY": ["breach", "vulnerability", "cve", "exploit", "authentication",
                 "authorization", "token", "oauth", "xss", "injection"],
    "MONITORING": ["alert", "prometheus", "grafana", "datadog", "metrics",
                   "logging", "traces", "apm", "sla", "uptime"],
    "APPLICATION": ["crash", "oom", "memory leak", "heap", "stack trace",
                    "exception", "error", "bug", "regression", "performance"],
    "INFRASTRUCTURE": ["aws", "gcp", "azure", "terraform", "ansible",
                       "ci/cd", "pipeline", "deploy", "scaling", "autoscale"],
}


def detect_domain(text: str) -> str:
    """Classify text into a domain based on keyword matching."""
    text_lower = text.lower()
    scores: Dict[str, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[domain] = score
    if not scores:
        return "GENERAL"
    return max(scores, key=scores.get)


# ── Quality Validation (from CascadeFlow strategy) ────────────────────────

class QualityValidator:
    """
    Multi-dimensional quality validation for AI responses.
    Inspired by CascadeFlow's quality validation engine.
    """

    @staticmethod
    def validate(response: str, query: str) -> Dict[str, Any]:
        """Validate response quality across multiple dimensions."""
        checks: Dict[str, bool] = {}
        confidence = 0.0

        # Length check
        checks["sufficient_length"] = len(response) > 50
        if checks["sufficient_length"]:
            confidence += 0.2

        # Completeness — contains actionable content
        action_keywords = ["step", "action", "recommend", "cause", "fix",
                           "solution", "check", "run", "verify", "ensure"]
        action_count = sum(1 for kw in action_keywords if kw in response.lower())
        checks["has_actionable_content"] = action_count >= 2
        if checks["has_actionable_content"]:
            confidence += 0.3

        # Relevance — response relates to query
        query_words = set(query.lower().split())
        response_words = set(response.lower().split())
        overlap = len(query_words & response_words)
        relevance = overlap / max(len(query_words), 1)
        checks["is_relevant"] = relevance > 0.15
        if checks["is_relevant"]:
            confidence += 0.25

        # Structure — has formatting (headers, lists, code blocks)
        has_structure = any(marker in response for marker in ["**", "##", "- ", "1.", "```", "\n\n"])
        checks["is_structured"] = has_structure
        if checks["is_structured"]:
            confidence += 0.25

        passed = sum(checks.values()) >= 3
        return {
            "passed": passed,
            "confidence": min(confidence, 1.0),
            "checks": checks,
        }


# ── Model Success Tracker (Self-Improving Routing) ────────────────────────

class ModelSuccessTracker:
    """
    Tracks which model tiers produce the best results per domain.
    Inspired by CascadeFlow's self-improving agent intelligence.
    """
    # In-memory tracking (persisted to DB via learning engine)
    _domain_stats: Dict[str, Dict[str, Dict[str, float]]] = {}

    @classmethod
    def record_outcome(cls, domain: str, model_tier: str, quality_score: float):
        if domain not in cls._domain_stats:
            cls._domain_stats[domain] = {}
        if model_tier not in cls._domain_stats[domain]:
            cls._domain_stats[domain][model_tier] = {"total_score": 0.0, "count": 0}
        cls._domain_stats[domain][model_tier]["total_score"] += quality_score
        cls._domain_stats[domain][model_tier]["count"] += 1

    @classmethod
    def get_best_tier_for_domain(cls, domain: str) -> Optional[str]:
        if domain not in cls._domain_stats:
            return None
        stats = cls._domain_stats[domain]
        best_tier = None
        best_avg = 0.0
        for tier, data in stats.items():
            if data["count"] > 0:
                avg = data["total_score"] / data["count"]
                if avg > best_avg:
                    best_avg = avg
                    best_tier = tier
        return best_tier

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        result = {}
        for domain, tiers in cls._domain_stats.items():
            result[domain] = {}
            for tier, data in tiers.items():
                count = data["count"]
                avg = data["total_score"] / count if count > 0 else 0
                result[domain][tier] = {"avg_quality": round(avg, 3), "count": count}
        return result


# ── Conversation Learning Engine ──────────────────────────────────────────

class ConversationLearningEngine:
    """
    Learns from past conversations to improve future agent responses.
    Inspired by Vectorize Self-Driving Agents + Hindsight.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.memory = HindsightMemoryService(db)

    async def learn_from_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """
        Extract knowledge from a completed conversation and store it in memory.
        """
        stmt = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
        )
        result = await self.db.execute(stmt)
        conversation = result.scalar_one_or_none()
        if not conversation:
            return {"error": "Conversation not found"}

        messages = conversation.messages
        if not messages or len(messages) < 2:
            return {"error": "Not enough messages to learn from"}

        learnings_stored = []

        # Extract user queries and assistant responses
        pairs = []
        for i, msg in enumerate(messages):
            if msg.role == MessageRole.USER and i + 1 < len(messages):
                next_msg = messages[i + 1]
                if next_msg.role == MessageRole.ASSISTANT:
                    pairs.append((msg, next_msg))

        for user_msg, assistant_msg in pairs:
            domain = detect_domain(user_msg.content)

            # Track model success
            quality = QualityValidator.validate(assistant_msg.content, user_msg.content)
            if assistant_msg.model_tier:
                ModelSuccessTracker.record_outcome(
                    domain=domain,
                    model_tier=assistant_msg.model_tier,
                    quality_score=quality["confidence"],
                )

            # Store high-quality Q&A pairs as workflow knowledge
            if quality["passed"] and quality["confidence"] >= 0.6:
                content = (
                    f"Query: {user_msg.content[:500]}\n\n"
                    f"Successful Response Pattern:\n{assistant_msg.content[:1000]}\n\n"
                    f"Domain: {domain} | Model: {assistant_msg.model_used or 'unknown'} | "
                    f"Quality: {quality['confidence']:.0%}"
                )
                record = await self.memory.store(
                    category=MemoryCategory.WORKFLOW,
                    title=f"Learned pattern: {user_msg.content[:100]}",
                    content=content,
                    tags=[domain.lower(), "learned", "conversation-pattern"],
                    confidence_score=quality["confidence"],
                )
                learnings_stored.append(str(record.id))

        # Update conversation metadata
        conversation.learning_extracted = True
        domains = list({detect_domain(m.content) for m in messages if m.role == MessageRole.USER})
        conversation.domain_tags = domains
        await self.db.flush()

        logger.info("🧠 Learned %d patterns from conversation %s", len(learnings_stored), conversation_id)
        return {
            "conversation_id": conversation_id,
            "patterns_learned": len(learnings_stored),
            "domains_detected": domains,
            "model_stats": ModelSuccessTracker.get_stats(),
        }

    async def get_conversation_context(
        self, conversation_id: str, last_n: int = 10
    ) -> List[Dict[str, str]]:
        """Get recent messages from a conversation for context injection."""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(last_n)
        )
        result = await self.db.execute(stmt)
        messages = list(reversed(result.scalars().all()))
        return [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages
        ]
