import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { cn } from "../lib/utils";

export type SpaceTab = { to: string; label: string; count?: number; end?: boolean };

/** One sidebar space: a row of tabs over the selected view. Tabs are plain links, so every view keeps its own URL. */
export function Space({ tabs, children, scroll = true }: { tabs: SpaceTab[]; children: ReactNode; scroll?: boolean }) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <nav className="flex shrink-0 gap-1 overflow-x-auto border-b border-border px-4 pt-3" aria-label="Sections">
        {tabs.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) => cn("flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 pb-2 text-xs font-medium",
              isActive ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}
          >
            {t.label}
            {t.count ? <span className="rounded-full bg-warning/15 px-1.5 text-[10px] font-semibold text-warning">{t.count}</span> : null}
          </NavLink>
        ))}
      </nav>
      <div className={cn("min-h-0 flex-1", scroll && "scrollbar-thin overflow-auto")}>{children}</div>
    </div>
  );
}
