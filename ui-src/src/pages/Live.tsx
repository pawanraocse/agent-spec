import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Radio } from "lucide-react";
import { useLive, useRequest, useRequests, type Filters } from "../api/traces";
import { Num } from "../components/Num";
import { Button } from "../components/ui/button";
import { Empty } from "../components/ui/card";
import { RequestFeed } from "../features/RequestFeed";
import { RequestView } from "../features/RequestView";
import { cn, copyText } from "../lib/utils";

const SETUP = "./install.sh --register \"$(pwd)\"";

/** Live space (§14.2): request feed + the selected request as an orchestration graph. */
export function Live() {
  const { id } = useParams();
  const nav = useNavigate();
  const [filters, setFilters] = useState<Filters>({});
  const list = useRequests(filters);
  const live = useLive(true);
  const selected = id ? decodeURIComponent(id) : list.data?.requests[0]?.trace_id ?? null;
  const detail = useRequest(selected);

  useEffect(() => {
    if (!id && list.data?.requests[0]) nav(`/requests/${encodeURIComponent(list.data.requests[0].trace_id)}`, { replace: true });
  }, [id, list.data, nav]);

  const empty = list.data && list.data.total === 0 && !filters.q && !filters.source && !filters.skill && !filters.status;
  return (
    <div className="flex h-full min-h-0">
      <aside className="flex w-[340px] shrink-0 flex-col border-r border-border">
        <div className="flex items-center justify-between border-b border-border px-3 py-2">
          <h1 className="text-sm font-semibold">Live</h1>
          <span className={cn("inline-flex items-center gap-1.5 text-[11px]", live.state === "live" ? "text-success" : "text-muted-foreground")} title="Server-Sent Events on /api/live; falls back to 2 s polling">
            <Radio size={12} className={live.state === "live" ? "animate-pulse" : ""} />
            {live.state === "live" ? "streaming" : live.state}
            {live.rows ? <span className="text-muted-foreground">· <Num p="measured">{live.rows}</Num> events</span> : null}
          </span>
        </div>
        <div className="min-h-0 flex-1">
          <RequestFeed
            data={list.data}
            loading={list.isLoading}
            filters={filters}
            setFilters={setFilters}
            selected={selected}
            onSelect={(t) => nav(`/requests/${encodeURIComponent(t.trace_id)}`)}
          />
        </div>
      </aside>
      <section className="min-w-0 flex-1">
        {empty ? (
          <Empty
            title="No requests yet"
            hint={<>Register this workspace so Cursor's hooks write every prompt, tool call, subagent and response to <code>.agent-spec/metrics/events.jsonl</code>; requests then appear here as they happen. History from Cursor's local store appears after <code>agent-spec-platform.py ingest traces</code>.</>}
            action={<Button size="sm" variant="outline" onClick={() => copyText(SETUP)}>Copy: {SETUP}</Button>}
          />
        ) : detail.data ? (
          <RequestView key={detail.data.trace.trace_id} detail={detail.data} />
        ) : detail.isError ? (
          <Empty title="Request not found" hint="It may have been rotated out of events.jsonl." />
        ) : (
          <div className="p-6 text-xs text-muted-foreground">Loading request…</div>
        )}
      </section>
    </div>
  );
}
