import { Bot, Combine, FileEdit, MessageSquare, MessageSquareReply, Minimize2, ShieldAlert, Sparkles, Workflow, Wrench, ListChecks } from "lucide-react";
import type { SpanKind } from "../api/traces";

export const KIND: Record<SpanKind, { label: string; icon: typeof Bot; color: string; bg: string; bar: string }> = {
  prompt: { label: "Prompt", icon: MessageSquare, color: "text-k-prompt", bg: "bg-k-prompt/10", bar: "bg-k-prompt" },
  skill: { label: "Skill", icon: Sparkles, color: "text-k-skill", bg: "bg-k-skill/10", bar: "bg-k-skill" },
  subagent: { label: "Subagent", icon: Bot, color: "text-k-subagent", bg: "bg-k-subagent/10", bar: "bg-k-subagent" },
  tool: { label: "Tool", icon: Wrench, color: "text-k-tool", bg: "bg-k-tool/10", bar: "bg-k-tool" },
  guard: { label: "Guard", icon: ShieldAlert, color: "text-k-guard", bg: "bg-k-guard/10", bar: "bg-k-guard" },
  edit: { label: "Edit", icon: FileEdit, color: "text-k-edit", bg: "bg-k-edit/10", bar: "bg-k-edit" },
  response: { label: "Response", icon: MessageSquareReply, color: "text-k-response", bg: "bg-k-response/10", bar: "bg-k-response" },
  compact: { label: "Compaction", icon: Minimize2, color: "text-k-compact", bg: "bg-k-compact/10", bar: "bg-k-compact" },
  workflow: { label: "Workflow", icon: Workflow, color: "text-k-workflow", bg: "bg-k-workflow/10", bar: "bg-k-workflow" },
  run_step: { label: "Run step", icon: ListChecks, color: "text-k-workflow", bg: "bg-k-workflow/10", bar: "bg-k-workflow" },
};

export const GROUP_ICON = Combine;

export function kindMeta(kind: string) {
  return KIND[kind as SpanKind] ?? KIND.tool;
}

export function statusTone(status: string): "success" | "danger" | "warning" | "primary" | "neutral" {
  if (["ok", "completed", "success"].includes(status)) return "success";
  if (["error", "failed", "blocked", "aborted"].includes(status)) return "danger";
  if (["incomplete", "self_healed", "waiting"].includes(status)) return "warning";
  if (status === "running") return "primary";
  return "neutral";
}

export const STATUS_RING: Record<string, string> = {
  success: "ring-success/50",
  danger: "ring-danger/70",
  warning: "ring-warning/60",
  primary: "ring-primary/70",
  neutral: "ring-border",
};
