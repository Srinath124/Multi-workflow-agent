import type { Conversation, ConversationDetail, ChatResponse, LearningStats } from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Original types (kept for backward compatibility) ─────────────────────

export interface IncidentCreate {
  title: string;
  description: string;
  severity: "low" | "medium" | "high" | "critical";
  service?: string;
  environment?: string;
}

export interface Memory {
  id: string;
  category: string;
  title: string;
  content: string;
  tags: string[];
  similarity_score?: number;
  retrieval_count?: number;
  confidence_score?: number;
  created_at: string;
}

export interface Stats {
  total_incidents: number;
  resolved: number;
  open: number;
  critical: number;
  total_ai_cost_usd: number;
}

// ── HTTP helper ──────────────────────────────────────────────────────────

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${msg}`);
  }
  return res.json() as Promise<T>;
}

// ── API Client ───────────────────────────────────────────────────────────

export const api = {
  // ── Chat ──
  sendMessage: (message: string, conversationId?: string) =>
    request<ChatResponse>("/api/v1/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        conversation_id: conversationId || undefined,
      }),
    }),

  // ── Conversations ──
  listConversations: (limit = 50) =>
    request<Conversation[]>(`/api/v1/conversations?limit=${limit}`),

  getConversation: (id: string) =>
    request<ConversationDetail>(`/api/v1/conversations/${id}`),

  renameConversation: (id: string, title: string) =>
    request<{ id: string; title: string }>(`/api/v1/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),

  deleteConversation: (id: string) =>
    request<{ deleted: boolean }>(`/api/v1/conversations/${id}`, {
      method: "DELETE",
    }),

  learnFromConversation: (id: string) =>
    request(`/api/v1/conversations/${id}/learn`, { method: "POST" }),

  // ── Learning Stats ──
  getLearningStats: () => request<LearningStats>("/api/v1/learning/stats"),

  // ── Legacy incident endpoints ──
  createIncident: (payload: IncidentCreate) =>
    request("/api/v1/incidents", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listIncidents: (params?: { status?: string; severity?: string }) => {
    const qs = params
      ? "?" + new URLSearchParams(params as Record<string, string>).toString()
      : "";
    return request(`/api/v1/incidents${qs}`);
  },

  getStats: () => request<Stats>("/api/v1/incidents/stats/summary"),

  searchMemory: (query: string) =>
    request<{ results: Memory[]; count: number }>("/api/v1/memory/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k: 10 }),
    }),

  listMemory: () =>
    request<{ records: Memory[]; count: number }>("/api/v1/memory"),

  health: () => request<{ status: string }>("/api/v1/health"),
};
