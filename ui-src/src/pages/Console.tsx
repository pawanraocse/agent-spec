import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { useState } from "react";
import {
  Copy,
  Check,
} from "lucide-react";

const PERSONAS = [
  { id: "ai-architect", label: "AI Architect", cmd: "/agent-spec-persona ai-architect" },
  { id: "code-reviewer", label: "Code Reviewer", cmd: "/agent-spec-persona code-reviewer" },
  { id: "rca-specialist", label: "RCA Specialist", cmd: "/agent-spec-persona rca-specialist" },
  { id: "test-engineer", label: "Test Engineer", cmd: "/agent-spec-persona test-engineer" },
  { id: "devsecops", label: "DevSecOps", cmd: "/agent-spec-persona devsecops" },
  { id: "none", label: "Standard Harness", cmd: "" },
];

const QUICK_COMMANDS = [
  { label: "Query Graph", cmd: "/agent-spec-query-graph", placeholder: "<symbol or file>" },
  { label: "Blast Radius", cmd: "/agent-spec-blast-radius", placeholder: "<file path>" },
  { label: "RCA Workflow", cmd: "/agent-spec-wf-rca", placeholder: "PROJ-123" },
  { label: "PR Review", cmd: "/agent-spec-wf-pr-review", placeholder: "feature/branch" },
  { label: "Session Snapshot", cmd: "/agent-spec-snapshot", placeholder: "" },
  { label: "Context Compact", cmd: "/agent-spec-compact", placeholder: "" },
];

export function Console() {
  const [selectedPersona, setSelectedPersona] = useState(PERSONAS[0].cmd);
  const [selectedCmd, setSelectedCmd] = useState("");
  const [promptArg, setPromptArg] = useState("");
  const [instruction, setInstruction] = useState("");
  const [copied, setCopied] = useState(false);

  // Generate composed slash command
  const fullCommand = [
    selectedPersona,
    selectedCmd ? `${selectedCmd} ${promptArg}`.trim() : "",
    instruction.trim(),
  ]
    .filter(Boolean)
    .join("\n\n");

  const copyToClipboard = async () => {
    if (!fullCommand) return;
    try {
      await navigator.clipboard.writeText(fullCommand);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      /* fallback */
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="border-b border-border pb-4">
        <div className="flex items-center gap-2">
          <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-semibold uppercase text-primary">
            DEC-15 AI-First
          </span>
          <span className="text-xs text-muted-foreground">Cursor is the Console</span>
        </div>
        <h1 className="mt-1 text-xl font-semibold text-foreground">Prompt & Workflow Composer</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Compose structured harness commands, personas, and workflows to drive Cursor natively.
        </p>
      </div>

      {/* Composer Grid */}
      <Card className="space-y-4 p-5 text-xs">
        {/* Step 1: Select Persona */}
        <div>
          <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground block mb-2">
            1. Select Agent Persona
          </label>
          <div className="grid gap-2 sm:grid-cols-3">
            {PERSONAS.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`rounded-lg border p-2.5 text-left transition-colors ${
                  selectedPersona === p.cmd
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border bg-background text-foreground/85 hover:bg-muted/60"
                }`}
                onClick={() => setSelectedPersona(p.cmd)}
              >
                <div className="font-medium text-foreground">{p.label}</div>
                <div className="font-mono text-[10px] text-muted-foreground mt-0.5">
                  {p.cmd || "(default)"}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Step 2: Quick Workflow or Command */}
        <div>
          <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground block mb-2">
            2. Choose Skill or Workflow (Optional)
          </label>
          <div className="grid gap-2 sm:grid-cols-3">
            {QUICK_COMMANDS.map((qc) => (
              <button
                key={qc.label}
                type="button"
                className={`rounded-lg border p-2 text-left transition-colors ${
                  selectedCmd === qc.cmd
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border bg-background text-foreground/85 hover:bg-muted/60"
                }`}
                onClick={() => {
                  if (selectedCmd === qc.cmd) {
                    setSelectedCmd("");
                    setPromptArg("");
                  } else {
                    setSelectedCmd(qc.cmd);
                    setPromptArg(qc.placeholder);
                  }
                }}
              >
                <div className="font-mono text-[11px] font-semibold text-foreground">{qc.cmd}</div>
                <div className="text-[10px] text-muted-foreground">{qc.label}</div>
              </button>
            ))}
          </div>
          {selectedCmd && (
            <div className="mt-2">
              <input
                className="w-full rounded-lg border border-border bg-background px-3 py-1.5 font-mono text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
                placeholder="Workflow arguments (e.g. Jira issue key or file path)..."
                value={promptArg}
                onChange={(e) => setPromptArg(e.target.value)}
              />
            </div>
          )}
        </div>

        {/* Step 3: Instructions */}
        <div>
          <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground block mb-2">
            3. Task & Intent Description
          </label>
          <textarea
            className="w-full min-h-24 rounded-lg border border-border bg-background p-3 text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
            placeholder="Describe the task or instructions for the agent..."
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
          />
        </div>
      </Card>

      {/* Generated Preview & Copy Trigger */}
      <div className="space-y-3 rounded-xl border border-primary/30 bg-primary/10 p-5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-foreground/85">Generated Command Preview</span>
          <span className="text-[11px] text-muted-foreground font-mono">paste into Cursor chat</span>
        </div>

        <pre className="overflow-auto rounded-lg border border-border bg-background p-3 font-mono text-xs text-primary whitespace-pre-wrap max-h-40">
          {fullCommand || "(select options above to build command)"}
        </pre>

        <div className="flex items-center justify-between pt-1">
          <p className="text-xs text-muted-foreground">
            {copied ? (
              <span className="text-success font-medium flex items-center gap-1.5">
                <Check size={14} /> Copied to clipboard! Switch to Cursor and paste (Cmd+V).
              </span>
            ) : (
              "Copy command and paste into your active Cursor chat window."
            )}
          </p>

          <Button
            type="button"
            size="sm"
            onClick={copyToClipboard}
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? "Copied!" : "Copy for Cursor"}
          </Button>
        </div>
      </div>
    </div>
  );
}
