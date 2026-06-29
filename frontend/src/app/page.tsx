import type { Metadata } from "next";
import ChatApp from "@/components/Dashboard";

export const metadata: Metadata = {
  title: "AI Incident Response Agent — Self-Learning Chat",
  description:
    "Production-grade AI agent with persistent memory, CascadeFlow routing, and conversation-driven self-improvement.",
};

export default function Home() {
  return <ChatApp />;
}
