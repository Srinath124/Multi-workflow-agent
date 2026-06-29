"""
Incident Response Agent — Orchestrator
Combines Hindsight memory + CascadeFlow runtime into the full reasoning pipeline.
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import logging
import uuid

from app.memory.hindsight import HindsightMemoryService
from app.runtime.cascadeflow import CascadeFlowRuntime, ModelTier
from app.models.incident import Incident, IncidentStatus, Severity
from app.models.memory_record import MemoryCategory

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an elite AI Incident Response Engineer with years of experience in production systems.

Your responsibilities:
- Analyze infrastructure incidents with precision
- Retrieve and apply organizational knowledge from memory
- Provide actionable, specific resolution steps
- Identify root causes, not just symptoms
- Learn from every incident to prevent future occurrences

When analyzing an incident:
1. State the likely root cause clearly
2. Give numbered, specific resolution steps (include commands where appropriate)
3. Identify contributing factors
4. Suggest monitoring/alerting improvements
5. Extract lessons for future prevention

Be direct, technical, and specific. Engineers need to act immediately."""


class IncidentResponseAgent:
    def __init__(self, db: AsyncSession, budget_used_today: float = 0.0):
        self.db = db
        self.memory = HindsightMemoryService(db)
        self.runtime = CascadeFlowRuntime(budget_used_today)

    async def process_incident(
        self,
        title: str,
        description: str,
        severity: str = "medium",
        service: str = "unknown",
        environment: str = "production",
        incident_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full 10-step reasoning pipeline for an incoming incident.
        """
        logger.info("🚨 Processing incident: %s", title)
        pipeline_log: List[str] = []

        # Step 1 — Understand objective
        pipeline_log.append("Step 1: Analyzing incident objective and metadata")

        # Step 2 — Retrieve relevant historical knowledge
        pipeline_log.append("Step 2: Retrieving organizational memory")
        memory_results = await self.memory.retrieve(
            query=f"{title} {description} {service}",
            top_k=5,
        )
        pipeline_log.append(f"  → Found {len(memory_results)} relevant memories")

        # Step 3 — Determine memory relevance
        pipeline_log.append("Step 3: Evaluating memory relevance")
        high_confidence_memories = [m for m in memory_results if m["similarity_score"] >= 0.8]
        memory_context = ""
        if memory_results:
            memory_context = "\n\n## Relevant Organizational Memory:\n"
            for i, mem in enumerate(memory_results, 1):
                memory_context += (
                    f"\n### Memory {i} [{mem['category'].upper()}] "
                    f"(similarity: {mem['similarity_score']:.0%})\n"
                    f"**{mem['title']}**\n{mem['content']}\n"
                )
            pipeline_log.append(f"  → {len(high_confidence_memories)} high-confidence memories (≥80% similarity)")

        # Step 4 — Estimate complexity
        pipeline_log.append("Step 4: Estimating task complexity via CascadeFlow")
        incident_prompt = f"""
Incident Title: {title}
Service: {service}
Environment: {environment}
Severity: {severity}
Description: {description}
{memory_context}
"""

        # Step 5 — Route to best model
        decision = self.runtime.route(
            prompt=incident_prompt,
            memory_context_size=len(memory_results),
            estimated_tokens=1200,
        )
        pipeline_log.append(f"Step 5: Model selected — {decision.model.name} (tier: {decision.tier.value})")
        pipeline_log.append(f"  → Complexity: {decision.complexity_score:.2f} | Reason: {decision.routing_reason}")
        pipeline_log.append(f"  → Estimated cost: ${decision.estimated_cost_usd:.6f}")

        # Step 6 — Execute reasoning
        pipeline_log.append("Step 6: Executing incident analysis")
        llm_result = await self.runtime.invoke(
            decision=decision,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=incident_prompt,
        )

        # Step 7 — Validate output
        pipeline_log.append("Step 7: Validating AI response quality")
        analysis = llm_result["content"]
        is_valid = len(analysis) > 100 and any(
            kw in analysis.lower() for kw in ["cause", "action", "step", "fix", "resolution", "recommend"]
        )
        pipeline_log.append(f"  → Validation: {'✅ passed' if is_valid else '⚠️ low-quality response'}")

        # Step 8 — Extract structured fields
        pipeline_log.append("Step 8: Extracting structured insights")
        root_cause = self._extract_root_cause(analysis)
        resolution = self._extract_resolution(analysis)

        # Step 9 — Reflect
        pipeline_log.append("Step 9: Preparing memory reflection")

        # Step 10 — Store knowledge (called after user confirms resolution)
        pipeline_log.append("Step 10: Ready to store knowledge post-resolution")

        return {
            "incident_id": incident_id,
            "analysis": analysis,
            "root_cause": root_cause,
            "resolution": resolution,
            "model_used": llm_result["model"],
            "model_tier": decision.tier.value,
            "complexity_score": decision.complexity_score,
            "routing_reason": decision.routing_reason,
            "cost_usd": decision.estimated_cost_usd,
            "budget_remaining_usd": decision.budget_remaining_usd,
            "memory_hits": len(memory_results),
            "high_confidence_hits": len(high_confidence_memories),
            "similar_memories": memory_results,
            "pipeline_log": pipeline_log,
            "cascade_audit": decision.audit_log,
            "tokens_used": llm_result.get("tokens_used", 0),
            "is_from_memory": len(high_confidence_memories) > 0,
        }

    async def resolve_incident(
        self,
        incident_id: str,
        resolution_notes: str,
        root_cause: str,
        lessons: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Mark incident as resolved and commit knowledge to long-term memory.
        """
        from sqlalchemy import select
        stmt = select(Incident).where(Incident.id == uuid.UUID(incident_id))
        result = await self.db.execute(stmt)
        incident = result.scalar_one_or_none()
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        incident.status = IncidentStatus.RESOLVED
        incident.resolution = resolution_notes
        incident.root_cause = root_cause
        incident.resolved_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Store knowledge in long-term memory
        stored = await self.memory.reflect_and_store(
            incident_id=incident_id,
            incident_title=incident.title,
            root_cause=root_cause,
            resolution=resolution_notes,
            service=incident.service or "unknown",
            severity=incident.severity.value,
            lessons=lessons or [],
        )

        logger.info("✅ Incident %s resolved. Stored %d memories.", incident_id, len(stored))
        return {
            "incident_id": incident_id,
            "status": "resolved",
            "memories_stored": len(stored),
            "message": f"Knowledge committed to long-term memory ({len(stored)} records)",
        }

    async def process_chat_message(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Process a general chat message with full pipeline.
        Supports multi-turn context from conversation history.
        """
        logger.info("💬 Processing chat message: %s", message[:80])
        pipeline_log: List[str] = []

        # Step 1 — Understand the query
        pipeline_log.append("Step 1: Analyzing user query")

        # Step 2 — Retrieve relevant knowledge from memory
        pipeline_log.append("Step 2: Retrieving organizational memory")
        memory_results = await self.memory.retrieve(query=message, top_k=5)
        pipeline_log.append(f"  → Found {len(memory_results)} relevant memories")

        # Step 3 — Evaluate memory relevance
        pipeline_log.append("Step 3: Evaluating memory relevance")
        high_confidence_memories = [m for m in memory_results if m["similarity_score"] >= 0.8]
        memory_context = ""
        if memory_results:
            memory_context = "\n\n## Relevant Organizational Knowledge:\n"
            for i, mem in enumerate(memory_results, 1):
                memory_context += (
                    f"\n### Knowledge {i} [{mem['category'].upper()}] "
                    f"(relevance: {mem['similarity_score']:.0%})\n"
                    f"**{mem['title']}**\n{mem['content']}\n"
                )
            pipeline_log.append(f"  → {len(high_confidence_memories)} high-confidence matches (≥80%)")

        # Step 4 — Build conversation context
        pipeline_log.append("Step 4: Building conversation context")
        conv_context = ""
        if conversation_history and len(conversation_history) > 1:
            conv_context = "\n\n## Recent Conversation Context:\n"
            # Only include last few exchanges for context
            for msg in conversation_history[-6:]:
                role_label = "User" if msg["role"] == "user" else "Assistant"
                conv_context += f"\n**{role_label}:** {msg['content'][:500]}\n"
            pipeline_log.append(f"  → Using {min(len(conversation_history), 6)} messages for context")

        # Step 5 — Route to optimal model
        full_prompt = f"{message}\n{conv_context}\n{memory_context}"
        decision = self.runtime.route(
            prompt=full_prompt,
            memory_context_size=len(memory_results),
            estimated_tokens=1200,
        )
        pipeline_log.append(f"Step 5: Model selected — {decision.model.name} (tier: {decision.tier.value})")
        pipeline_log.append(f"  → Complexity: {decision.complexity_score:.2f} | Reason: {decision.routing_reason}")
        pipeline_log.append(f"  → Estimated cost: ${decision.estimated_cost_usd:.6f}")

        # Step 6 — Execute with full context
        pipeline_log.append("Step 6: Generating response")
        chat_system = SYSTEM_PROMPT + (
            "\n\nYou are also a knowledgeable AI assistant. "
            "Answer questions clearly and helpfully. "
            "If you have organizational memory or conversation context, use it to enrich your response."
        )
        llm_result = await self.runtime.invoke(
            decision=decision,
            system_prompt=chat_system,
            user_prompt=full_prompt,
        )

        # Step 7 — Validate quality
        pipeline_log.append("Step 7: Validating response quality")
        analysis = llm_result["content"]
        is_valid = len(analysis) > 30
        pipeline_log.append(f"  → Validation: {'✅ passed' if is_valid else '⚠️ short response'}")

        # Step 8 — Prepare response
        pipeline_log.append("Step 8: Response ready")

        return {
            "analysis": analysis,
            "model_used": llm_result["model"],
            "model_tier": decision.tier.value,
            "complexity_score": decision.complexity_score,
            "routing_reason": decision.routing_reason,
            "cost_usd": decision.estimated_cost_usd,
            "budget_remaining_usd": decision.budget_remaining_usd,
            "memory_hits": len(memory_results),
            "high_confidence_hits": len(high_confidence_memories),
            "similar_memories": memory_results,
            "pipeline_log": pipeline_log,
            "cascade_audit": decision.audit_log,
            "tokens_used": llm_result.get("tokens_used", 0),
            "is_from_memory": len(high_confidence_memories) > 0,
        }

    def _extract_root_cause(self, analysis: str) -> str:
        for marker in ["root cause", "likely cause", "cause:"]:
            idx = analysis.lower().find(marker)
            if idx >= 0:
                snippet = analysis[idx:idx + 400]
                lines = snippet.split("\n")
                return "\n".join(lines[:4]).strip()
        return analysis[:300]

    def _extract_resolution(self, analysis: str) -> str:
        for marker in ["recommended actions", "resolution", "steps:", "actions:"]:
            idx = analysis.lower().find(marker)
            if idx >= 0:
                snippet = analysis[idx:idx + 600]
                return snippet.strip()
        return analysis[-400:].strip()
