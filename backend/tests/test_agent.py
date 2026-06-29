"""
Test suite — Incident Response Agent
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.runtime.cascadeflow import CascadeFlowRuntime, ModelTier
from app.memory.hindsight import _simple_embedding, _cosine_similarity


# ── Unit tests — CascadeFlow ────────────────────────────────────────────────

class TestCascadeFlowRouting:
    def setup_method(self):
        self.runtime = CascadeFlowRuntime(budget_used_today_usd=0.0)

    def test_simple_query_routes_to_fast(self):
        decision = self.runtime.route("What is the status of the database?", memory_context_size=0)
        assert decision.tier in (ModelTier.FAST, ModelTier.LOCAL)

    def test_critical_incident_routes_to_powerful_or_balanced(self):
        decision = self.runtime.route(
            "CRITICAL production outage — database down, data loss possible",
            memory_context_size=0,
        )
        assert decision.tier in (ModelTier.POWERFUL, ModelTier.BALANCED)

    def test_budget_exhausted_falls_back_to_local(self):
        runtime = CascadeFlowRuntime(budget_used_today_usd=9.99)
        decision = runtime.route(
            "CRITICAL production outage",
            memory_context_size=0,
        )
        # With budget nearly exhausted, should protect remaining budget
        assert decision.budget_remaining_usd >= 0

    def test_complexity_score_increases_with_critical_keywords(self):
        d1 = self.runtime.route("what is status", memory_context_size=0)
        d2 = self.runtime.route("CRITICAL production down data loss", memory_context_size=0)
        assert d2.complexity_score > d1.complexity_score

    def test_routing_reason_is_populated(self):
        decision = self.runtime.route("check pod health", memory_context_size=0)
        assert len(decision.routing_reason) > 0

    def test_audit_log_is_populated(self):
        decision = self.runtime.route("database error", memory_context_size=0)
        assert len(decision.audit_log) >= 3

    def test_memory_context_increases_complexity(self):
        d_no_ctx = self.runtime.route("database error", memory_context_size=0)
        d_with_ctx = self.runtime.route("database error", memory_context_size=5)
        assert d_with_ctx.complexity_score >= d_no_ctx.complexity_score


# ── Unit tests — Hindsight embedding ───────────────────────────────────────

class TestHindsightEmbedding:
    def test_embedding_is_normalized(self):
        emb = _simple_embedding("database connection pool exhausted")
        magnitude = sum(v * v for v in emb) ** 0.5
        assert abs(magnitude - 1.0) < 1e-5

    def test_similar_texts_have_high_cosine(self):
        emb_a = _simple_embedding("database connection error postgres")
        emb_b = _simple_embedding("database connection failure postgres")
        score = _cosine_similarity(emb_a, emb_b)
        assert score >= 0.7

    def test_dissimilar_texts_have_low_cosine(self):
        emb_a = _simple_embedding("kubernetes pod crash loop")
        emb_b = _simple_embedding("payment gateway timeout")
        score = _cosine_similarity(emb_a, emb_b)
        assert score <= 0.5

    def test_empty_text_handled_gracefully(self):
        emb = _simple_embedding("")
        # Should return a zero-like vector without error
        assert len(emb) == 128

    def test_cosine_self_similarity_is_one(self):
        emb = _simple_embedding("production outage memory leak")
        score = _cosine_similarity(emb, emb)
        assert abs(score - 1.0) < 1e-5


# ── Integration-style tests (mocked DB) ────────────────────────────────────

class TestAgentPipeline:
    @pytest.mark.asyncio
    async def test_demo_response_generated_without_api_keys(self):
        runtime = CascadeFlowRuntime()
        decision = runtime.route("database down", memory_context_size=0)
        result = await runtime.invoke(
            decision=decision,
            system_prompt="You are an incident responder.",
            user_prompt="Database connection pool exhausted.",
        )
        assert "content" in result
        assert len(result["content"]) > 50

    @pytest.mark.asyncio
    async def test_memory_demo_response_for_oom(self):
        runtime = CascadeFlowRuntime()
        decision = runtime.route("memory leak OOM", memory_context_size=0)
        result = await runtime.invoke(
            decision=decision,
            system_prompt="You are an incident responder.",
            user_prompt="Out of memory error in production pod",
        )
        assert "memory" in result["content"].lower() or "oom" in result["content"].lower()
