"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { api } from "@/services/api";
import type {
  Conversation,
  ChatMessage,
  ChatResponse,
  DateGroup,
} from "@/types";
import { groupConversationsByDate, TIER_COLORS } from "@/types";
import {
  Plus,
  MessageSquare,
  Send,
  Trash2,
  Pencil,
  Check,
  X,
  ChevronDown,
  ChevronRight,
  Cpu,
  Brain,
  Zap,
  Sparkles,
  BarChart3,
  PanelLeftClose,
  PanelLeft,
  Loader2,
  Bot,
  User,
  AlertTriangle,
  Shield,
} from "lucide-react";

// ════════════════════════════════════════════════════════════════════════════
// MAIN CHAT APPLICATION
// ════════════════════════════════════════════════════════════════════════════

export default function ChatApp() {
  // State
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [expandedPipeline, setExpandedPipeline] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── Load conversations ─────────────────────────────────────────────────
  const loadConversations = useCallback(async () => {
    try {
      const data = await api.listConversations();
      setConversations(data);
    } catch {
      // Silently handle — API might not be running
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // ── Load conversation messages ─────────────────────────────────────────
  const loadConversation = useCallback(async (id: string) => {
    try {
      const data = await api.getConversation(id);
      setMessages(data.messages || []);
      setActiveConversationId(id);
    } catch {
      setMessages([]);
    }
  }, []);

  // ── Auto-scroll ────────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Send message ───────────────────────────────────────────────────────
  const sendMessage = async () => {
    const msg = inputValue.trim();
    if (!msg || isLoading) return;

    setInputValue("");
    setIsLoading(true);

    // Optimistic user message
    const tempUserMsg: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: msg,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const response: ChatResponse = await api.sendMessage(
        msg,
        activeConversationId || undefined
      );

      // If new conversation, update ID and reload sidebar
      if (!activeConversationId) {
        setActiveConversationId(response.conversation_id);
      }

      // Replace temp message with real ones
      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== tempUserMsg.id);
        return [...filtered, response.user_message, response.assistant_message];
      });

      // Reload conversations list
      await loadConversations();
    } catch (err) {
      // Show error as assistant message
      const errorMsg: ChatMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: `Sorry, I encountered an error: ${err instanceof Error ? err.message : "Unknown error"}. Please try again.`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  // ── New conversation ───────────────────────────────────────────────────
  const startNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setInputValue("");
    inputRef.current?.focus();
  };

  // ── Delete conversation ────────────────────────────────────────────────
  const deleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.deleteConversation(id);
      if (activeConversationId === id) {
        startNewChat();
      }
      await loadConversations();
    } catch { /* ignore */ }
  };

  // ── Rename conversation ────────────────────────────────────────────────
  const startRename = (id: string, currentTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(id);
    setEditTitle(currentTitle);
  };

  const saveRename = async (id: string) => {
    if (editTitle.trim()) {
      try {
        await api.renameConversation(id, editTitle.trim());
        await loadConversations();
      } catch { /* ignore */ }
    }
    setEditingId(null);
  };

  // ── Handle Enter key ──────────────────────────────────────────────────
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ── Group conversations ────────────────────────────────────────────────
  const grouped = groupConversationsByDate(conversations);
  const dateGroups: DateGroup[] = [
    "Today",
    "Yesterday",
    "Previous 7 Days",
    "Previous 30 Days",
    "Older",
  ];

  // ════════════════════════════════════════════════════════════════════════
  // RENDER
  // ════════════════════════════════════════════════════════════════════════

  return (
    <div className="flex h-screen overflow-hidden bg-[#0a0a0f]">
      {/* ── SIDEBAR ──────────────────────────────────────────────────── */}
      <aside
        className={`${
          isSidebarOpen ? "w-[280px]" : "w-0"
        } flex-shrink-0 transition-all duration-300 overflow-hidden`}
      >
        <div className="flex flex-col h-full w-[280px] bg-[#0f0f18] border-r border-white/[0.06]">
          {/* New Chat Button */}
          <div className="p-3">
            <button
              onClick={startNewChat}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-violet-600/20 to-cyan-600/20 border border-violet-500/20 hover:border-violet-400/40 text-sm font-medium text-gray-200 hover:text-white transition-all duration-200 group"
            >
              <Plus size={18} className="text-violet-400 group-hover:text-violet-300" />
              New Chat
            </button>
          </div>

          {/* Conversation List */}
          <div className="flex-1 overflow-y-auto px-2 pb-4 scrollbar-thin">
            {dateGroups.map((group) => {
              const items = grouped[group];
              if (items.length === 0) return null;
              return (
                <div key={group} className="mb-2">
                  <div className="px-3 py-2 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                    {group}
                  </div>
                  {items.map((conv) => (
                    <div
                      key={conv.id}
                      onClick={() => loadConversation(conv.id)}
                      className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-150 mx-1 ${
                        activeConversationId === conv.id
                          ? "bg-white/[0.08] text-white"
                          : "text-gray-400 hover:bg-white/[0.04] hover:text-gray-200"
                      }`}
                    >
                      <MessageSquare size={14} className="flex-shrink-0 opacity-50" />
                      {editingId === conv.id ? (
                        <div className="flex-1 flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                          <input
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && saveRename(conv.id)}
                            className="flex-1 bg-white/10 border border-white/20 rounded px-2 py-0.5 text-xs text-white focus:outline-none focus:border-violet-400"
                            autoFocus
                          />
                          <button onClick={() => saveRename(conv.id)}>
                            <Check size={12} className="text-emerald-400" />
                          </button>
                          <button onClick={() => setEditingId(null)}>
                            <X size={12} className="text-gray-500" />
                          </button>
                        </div>
                      ) : (
                        <>
                          <span className="flex-1 text-sm truncate">{conv.title}</span>
                          <div className="hidden group-hover:flex items-center gap-1">
                            <button
                              onClick={(e) => startRename(conv.id, conv.title, e)}
                              className="p-1 rounded hover:bg-white/10 transition-colors"
                            >
                              <Pencil size={12} className="text-gray-500 hover:text-gray-300" />
                            </button>
                            <button
                              onClick={(e) => deleteConversation(conv.id, e)}
                              className="p-1 rounded hover:bg-red-500/20 transition-colors"
                            >
                              <Trash2 size={12} className="text-gray-500 hover:text-red-400" />
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              );
            })}

            {conversations.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-gray-600">
                <MessageSquare size={28} className="mb-3 opacity-40" />
                <p className="text-xs">No conversations yet</p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-3 border-t border-white/[0.06]">
            <div className="flex items-center gap-2 px-3 py-2 text-[11px] text-gray-500">
              <Sparkles size={12} className="text-violet-400" />
              <span>Self-Learning AI Agent</span>
            </div>
          </div>
        </div>
      </aside>

      {/* ── MAIN AREA ────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.06] bg-[#0a0a0f]/80 backdrop-blur-xl">
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="p-2 rounded-lg hover:bg-white/[0.06] text-gray-400 hover:text-gray-200 transition-colors"
          >
            {isSidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
          </button>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center">
              <Bot size={14} className="text-white" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-gray-200">Incident Response Agent</h1>
              <p className="text-[10px] text-gray-500">Memory-powered · CascadeFlow routing</p>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] font-medium text-emerald-400">Online</span>
            </div>
          </div>
        </header>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            /* ── Empty State ──────────────────────────────────────── */
            <div className="flex flex-col items-center justify-center h-full px-6">
              <div className="max-w-lg text-center">
                <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-violet-500/20 to-cyan-500/20 border border-white/[0.08] flex items-center justify-center">
                  <Sparkles size={28} className="text-violet-400" />
                </div>
                <h2 className="text-2xl font-bold text-white mb-2">AI Incident Response Agent</h2>
                <p className="text-gray-400 text-sm mb-8">
                  Powered by persistent memory & intelligent model routing. I learn from every conversation to get smarter over time.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {[
                    { icon: AlertTriangle, title: "Report Incident", desc: "Analyze production issues", color: "from-red-500/20 to-orange-500/20", borderColor: "border-red-500/20" },
                    { icon: Brain, title: "Search Memory", desc: "Recall past solutions", color: "from-violet-500/20 to-purple-500/20", borderColor: "border-violet-500/20" },
                    { icon: Shield, title: "Ask Anything", desc: "Infrastructure & DevOps", color: "from-cyan-500/20 to-blue-500/20", borderColor: "border-cyan-500/20" },
                  ].map(({ icon: Icon, title, desc, color, borderColor }) => (
                    <button
                      key={title}
                      onClick={() => {
                        setInputValue(
                          title === "Report Incident"
                            ? "PostgreSQL connection pool exhausted — 500 errors on API"
                            : title === "Search Memory"
                            ? "What do we know about database connection issues?"
                            : "How should we set up monitoring for our Kubernetes cluster?"
                        );
                        inputRef.current?.focus();
                      }}
                      className={`p-4 rounded-xl bg-gradient-to-br ${color} border ${borderColor} hover:border-white/20 text-left transition-all duration-200 group`}
                    >
                      <Icon size={20} className="text-gray-300 mb-2 group-hover:text-white transition-colors" />
                      <div className="text-sm font-medium text-gray-200">{title}</div>
                      <div className="text-[11px] text-gray-500 mt-0.5">{desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            /* ── Messages ─────────────────────────────────────────── */
            <div className="max-w-3xl mx-auto px-4 py-6">
              {messages.map((msg) => (
                <div key={msg.id} className={`mb-6 ${msg.role === "user" ? "flex justify-end" : ""}`}>
                  {msg.role === "user" ? (
                    /* User Message */
                    <div className="max-w-[85%]">
                      <div className="flex items-start gap-3 justify-end">
                        <div className="px-4 py-3 rounded-2xl rounded-tr-md bg-violet-600/30 border border-violet-500/20 text-gray-100 text-sm whitespace-pre-wrap">
                          {msg.content}
                        </div>
                        <div className="w-8 h-8 rounded-full bg-violet-600/30 border border-violet-500/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                          <User size={14} className="text-violet-300" />
                        </div>
                      </div>
                    </div>
                  ) : (
                    /* Assistant Message */
                    <div className="max-w-full">
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500/30 to-violet-500/30 border border-cyan-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                          <Bot size={14} className="text-cyan-300" />
                        </div>
                        <div className="flex-1 min-w-0">
                          {/* Memory recall banner */}
                          {msg.high_confidence_hits && msg.high_confidence_hits > 0 && (
                            <div className="flex items-center gap-2 mb-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 w-fit">
                              <Brain size={12} className="text-amber-400" />
                              <span className="text-[11px] font-medium text-amber-300">
                                Recalled {msg.high_confidence_hits} similar {msg.high_confidence_hits === 1 ? "memory" : "memories"} from past experience
                              </span>
                            </div>
                          )}

                          {/* Message content */}
                          <div className="text-sm text-gray-200 whitespace-pre-wrap leading-relaxed prose-invert">
                            {msg.content}
                          </div>

                          {/* Metadata bar */}
                          {msg.model_used && (
                            <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-white/[0.04]">
                              {/* Model badge */}
                              {msg.model_tier && (
                                <span
                                  className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium ${
                                    TIER_COLORS[msg.model_tier]?.bg || "bg-gray-500/20"
                                  } ${TIER_COLORS[msg.model_tier]?.text || "text-gray-400"}`}
                                >
                                  <Cpu size={10} />
                                  {msg.model_used}
                                </span>
                              )}

                              {/* Cost */}
                              {msg.cost_usd !== undefined && msg.cost_usd !== null && (
                                <span className="text-[10px] text-gray-500">
                                  ${msg.cost_usd.toFixed(6)}
                                </span>
                              )}

                              {/* Tokens */}
                              {msg.tokens_used ? (
                                <span className="text-[10px] text-gray-500">
                                  {msg.tokens_used} tokens
                                </span>
                              ) : null}

                              {/* Domain */}
                              {msg.domain_detected && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.04] text-gray-500">
                                  {msg.domain_detected}
                                </span>
                              )}

                              {/* Quality */}
                              {msg.confidence_score !== undefined && msg.confidence_score !== null && (
                                <span className={`text-[10px] ${msg.quality_passed ? "text-emerald-500" : "text-amber-500"}`}>
                                  Quality: {(msg.confidence_score * 100).toFixed(0)}%
                                </span>
                              )}

                              {/* Pipeline toggle */}
                              {msg.pipeline_log && msg.pipeline_log.length > 0 && (
                                <button
                                  onClick={() =>
                                    setExpandedPipeline(
                                      expandedPipeline === msg.id ? null : msg.id
                                    )
                                  }
                                  className="inline-flex items-center gap-1 text-[10px] text-gray-500 hover:text-gray-300 transition-colors"
                                >
                                  <BarChart3 size={10} />
                                  {expandedPipeline === msg.id ? "Hide" : "View"} reasoning
                                  {expandedPipeline === msg.id ? (
                                    <ChevronDown size={10} />
                                  ) : (
                                    <ChevronRight size={10} />
                                  )}
                                </button>
                              )}
                            </div>
                          )}

                          {/* Pipeline log (expanded) */}
                          {expandedPipeline === msg.id && msg.pipeline_log && (
                            <div className="mt-3 p-3 rounded-lg bg-[#12121e] border border-white/[0.06] text-[11px] font-mono text-gray-400 space-y-1">
                              {msg.pipeline_log.map((line, i) => (
                                <div key={i} className={line.startsWith("Step") ? "text-cyan-400 font-semibold" : "pl-2"}>
                                  {line}
                                </div>
                              ))}
                              {msg.cascade_audit && msg.cascade_audit.length > 0 && (
                                <>
                                  <div className="border-t border-white/[0.06] mt-2 pt-2 text-violet-400 font-semibold">
                                    CascadeFlow Audit Trail
                                  </div>
                                  {msg.cascade_audit.map((line, i) => (
                                    <div key={`audit-${i}`} className="pl-2">
                                      {line}
                                    </div>
                                  ))}
                                </>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {/* Typing indicator */}
              {isLoading && (
                <div className="mb-6">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500/30 to-violet-500/30 border border-cyan-500/20 flex items-center justify-center flex-shrink-0">
                      <Bot size={14} className="text-cyan-300" />
                    </div>
                    <div className="px-4 py-3 rounded-2xl bg-white/[0.04] border border-white/[0.06]">
                      <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                        <div className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                        <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="px-4 pb-4 pt-2">
          <div className="max-w-3xl mx-auto">
            <div className="relative flex items-end gap-2 p-2 rounded-2xl bg-[#14141f] border border-white/[0.08] focus-within:border-violet-500/30 transition-colors shadow-lg shadow-black/20">
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe an incident or ask anything..."
                rows={1}
                className="flex-1 bg-transparent text-sm text-gray-200 placeholder-gray-600 resize-none outline-none px-3 py-2.5 max-h-32 scrollbar-thin"
                style={{ minHeight: "42px" }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = "auto";
                  target.style.height = Math.min(target.scrollHeight, 128) + "px";
                }}
              />
              <button
                onClick={sendMessage}
                disabled={!inputValue.trim() || isLoading}
                className="flex-shrink-0 w-9 h-9 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-gray-700 disabled:cursor-not-allowed flex items-center justify-center transition-colors"
              >
                {isLoading ? (
                  <Loader2 size={16} className="text-white animate-spin" />
                ) : (
                  <Send size={14} className="text-white" />
                )}
              </button>
            </div>
            <p className="text-center text-[10px] text-gray-600 mt-2">
              Powered by CascadeFlow routing · Hindsight memory · Self-learning agent
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
