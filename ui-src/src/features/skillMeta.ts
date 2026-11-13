import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import {
  BookOpen, Brain, Bug, FileText, FlaskConical, Gauge, Gavel, GitBranch, ListChecks, Search, Shield,
  Sparkles, Workflow, Wrench, type LucideIcon,
} from "lucide-react";
import { apiGet } from "../api/client";

/** One skill as `/api/catalog` serves it: SKILL.md header plus its `dashboard:` block (DV-055). */
export type Skill = {
  id: string; name: string; description: string; category: string; icon: string;
  emits: string[]; steps: string[]; self_described: boolean; is_workflow: boolean; uses: number;
};

// A curated set, not all of lucide: importing every icon by name would ship the whole library.
// An unknown name falls back to the span kind's own icon.
const ICONS: Record<string, LucideIcon> = {
  "book-open": BookOpen, brain: Brain, bug: Bug, "file-text": FileText, flask: FlaskConical, gauge: Gauge,
  gavel: Gavel, "git-branch": GitBranch, "list-checks": ListChecks, search: Search, shield: Shield,
  sparkles: Sparkles, workflow: Workflow, wrench: Wrench,
};

export const skillIcon = (name?: string | null): LucideIcon | null => (name ? ICONS[name] ?? null : null);

/** The catalog keyed by skill name and folder id; shared cache with Project › Skills. */
export function useCatalog(): Map<string, Skill> {
  const q = useQuery({
    queryKey: ["catalog"],
    queryFn: () => apiGet<{ skills: Skill[]; self_described: number }>("/api/catalog"),
    staleTime: 60_000,
  });
  return useMemo(() => {
    const map = new Map<string, Skill>();
    for (const s of q.data?.skills ?? []) {
      map.set(s.name, s);
      map.set(s.id, s);
    }
    return map;
  }, [q.data]);
}
