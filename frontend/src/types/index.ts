// ── Type Definitions ─────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  model_used?: string;
  model_tier?: string;
  complexity_score?: number;
  cost_usd?: number;
  tokens_used?: number;
  routing_reason?: string;
  memory_hits?: number;
  high_confidence_hits?: number;
  pipeline_log?: string[];
  cascade_audit?: string[];
  quality_passed?: boolean;
  confidence_score?: number;
  domain_detected?: string;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  message_count: number;
  total_cost_usd: number;
  model_tiers_used?: string[];
  domain_tags?: string[];
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: ChatMessage[];
}

export interface ChatResponse {
  conversation_id: string;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  error?: string;
}

export interface LearningStats {
  model_stats: Record<string, Record<string, { avg_quality: number; count: number }>>;
  description: string;
}

// Date grouping for sidebar
export type DateGroup = "Today" | "Yesterday" | "Previous 7 Days" | "Previous 30 Days" | "Older";

export function getDateGroup(dateStr: string): DateGroup {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays <= 7) return "Previous 7 Days";
  if (diffDays <= 30) return "Previous 30 Days";
  return "Older";
}

export function groupConversationsByDate(
  conversations: Conversation[]
): Record<DateGroup, Conversation[]> {
  const groups: Record<DateGroup, Conversation[]> = {
    Today: [],
    Yesterday: [],
    "Previous 7 Days": [],
    "Previous 30 Days": [],
    Older: [],
  };
  for (const conv of conversations) {
    const group = getDateGroup(conv.updated_at);
    groups[group].push(conv);
  }
  return groups;
}

// Tier colors
export const TIER_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  local: { bg: "bg-emerald-500/20", text: "text-emerald-400", label: "Local" },
  fast: { bg: "bg-cyan-500/20", text: "text-cyan-400", label: "Fast" },
  balanced: { bg: "bg-amber-500/20", text: "text-amber-400", label: "Balanced" },
  powerful: { bg: "bg-purple-500/20", text: "text-purple-400", label: "Powerful" },
};
