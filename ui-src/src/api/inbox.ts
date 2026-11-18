import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";
import type { RiskData } from "../pages/Risk";
import type { ProposalsData } from "../pages/Proposals";

/** Waiting on a person: blocked risky edits and learning-loop proposals. Shared by the sidebar badge and the Inbox tabs. */
export function useInboxCounts() {
  const risk = useQuery({ queryKey: ["risk"], queryFn: () => apiGet<RiskData>("/api/risk"), refetchInterval: 15000 });
  const props = useQuery({ queryKey: ["proposals"], queryFn: () => apiGet<ProposalsData>("/api/proposals"), refetchInterval: 15000 });
  const r = risk.data?.pending.length ?? 0, p = props.data?.pending.length ?? 0;
  return { risk: r, proposals: p, total: r + p };
}
