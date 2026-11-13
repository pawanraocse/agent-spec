import { Bot, ShieldAlert, Wrench, AlertTriangle, Search } from "lucide-react";
import type { Filters, RequestList, Trace } from "../api/traces";
import { Num } from "../components/Num";
import { Badge } from "../components/ui/badge";
import { cn, fmtMs, relTime } from "../lib/utils";
import { statusTone } from "./kinds";

const SOURCE_LABEL: Record<string, string> = { hook: "Live hook", cursor_store: "Cursor store", run: "Workflow", demo_seed: "Demo" };

/** DV-030: live request list. Status, duration, skills, subagent count per row. */
export function RequestFeed({ data, loading, filters, setFilters, selected, onSelect }: {
  data?: RequestList;
  loading: boolean;
  filters: Filters;
  setFilters: (f: Filters) => void;
  selected: string | null;
  onSelect: (t: Trace) => void;
}) {
  const facets = data?.facets;
  const select = (key: keyof Filters, values: string[] | undefined, label: string) =>
    values && values.length > 1 ? (
      <select
        aria-label={label}
        value={filters[key] ?? ""}
        onChange={(e) => setFilters({ ...filters, [key]: e.target.value || undefined })}
        className="h-7 rounded-md border border-border bg-background px-1.5 text-xs"
      >
        <option value="">{label}</option>
        {values.map((v) => <option key={v} value={v}>{key === "source" ? SOURCE_LABEL[v] ?? v : key === "workspace" ? v.split("/").pop() : v}</option>)}
      </select>
    ) : null;
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="space-y-2 border-b border-border p-3">
        <label className="flex h-8 items-center gap-2 rounded-md border border-border bg-background px-2 text-xs focus-within:ring-2 focus-within:ring-ring">
          <Search size={13} className="text-muted-foreground" />
          <input
            value={filters.q ?? ""}
            onChange={(e) => setFilters({ ...filters, q: e.target.value || undefined })}
            placeholder="Search prompts, ids, models"
            className="w-full bg-transparent outline-none placeholder:text-muted-foreground"
          />
        </label>
        <div className="flex flex-wrap gap-1.5">
          {select("source", facets?.sources, "All sources")}
          {select("status", facets?.statuses, "Any status")}
          {select("skill", facets?.skills, "Any skill")}
          {select("workspace", facets?.workspaces, "All workspaces")}
        </div>
        <p className="text-[11px] text-muted-foreground">
          {loading ? "Loading…" : <><Num p="measured">{data?.total ?? 0}</Num> requests</>}
        </p>
      </div>
      <ul className="scrollbar-thin min-h-0 flex-1 overflow-auto">
        {(data?.requests ?? []).map((t) => (
          <li key={t.trace_id}>
            <button
              type="button"
              onClick={() => onSelect(t)}
              className={cn("w-full border-b border-border/60 px-3 py-2.5 text-left transition-colors hover:bg-muted/50", selected === t.trace_id && "bg-primary/10 hover:bg-primary/10")}
            >
              <div className="flex items-center gap-2">
                <span className={cn("h-2 w-2 shrink-0 rounded-full", {
                  "bg-success": statusTone(t.status) === "success",
                  "bg-danger": statusTone(t.status) === "danger",
                  "bg-warning": statusTone(t.status) === "warning",
                  "animate-pulse bg-primary": t.status === "running",
                  "bg-muted-foreground": statusTone(t.status) === "neutral",
                })} />
                <span className="line-clamp-1 text-xs font-medium">{(t.prompt || t.session_name || "(prompt not captured)").replace(/\s+/g, " ")}</span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 pl-4 text-[10px] text-muted-foreground">
                <span>{relTime(t.start)}</span>
                <span><Num p={t.provenance}>{fmtMs(t.duration_ms)}</Num></span>
                <span className="inline-flex items-center gap-0.5"><Wrench size={10} /><Num p="measured">{t.tool_count}</Num></span>
                {t.subagent_count ? <span className="inline-flex items-center gap-0.5 text-k-subagent"><Bot size={10} /><Num p="measured">{t.subagent_count}</Num></span> : null}
                {t.guard_count ? <span className="inline-flex items-center gap-0.5 text-k-guard"><ShieldAlert size={10} /><Num p="measured">{t.guard_count}</Num></span> : null}
                {t.error_count ? <span className="inline-flex items-center gap-0.5 text-danger"><AlertTriangle size={10} /><Num p="measured">{t.error_count}</Num></span> : null}
                {t.skills.slice(0, 2).map((s) => <Badge key={s} tone="accent" className="normal-case">{s.replace(/^agent-spec-/, "")}</Badge>)}
                <span className="ml-auto">{SOURCE_LABEL[t.source] ?? t.source}</span>
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
