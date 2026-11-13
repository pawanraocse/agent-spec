import * as T from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

export const TooltipProvider = T.Provider;
export function Tip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <T.Root delayDuration={200}>
      <T.Trigger asChild>{children}</T.Trigger>
      <T.Portal>
        <T.Content sideOffset={6} className="z-50 max-w-xs rounded-md border border-border bg-card px-2 py-1 text-xs text-foreground shadow-lg">
          {content}
        </T.Content>
      </T.Portal>
    </T.Root>
  );
}
