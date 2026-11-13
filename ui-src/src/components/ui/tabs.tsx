import * as T from "@radix-ui/react-tabs";
import type { ComponentProps } from "react";
import { cn } from "../../lib/utils";

export const Tabs = T.Root;
export function TabsList({ className, ...p }: ComponentProps<typeof T.List>) {
  return <T.List className={cn("inline-flex items-center gap-1 rounded-md bg-muted p-1", className)} {...p} />;
}
export function TabsTrigger({ className, ...p }: ComponentProps<typeof T.Trigger>) {
  return (
    <T.Trigger
      className={cn(
        "rounded px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm",
        className,
      )}
      {...p}
    />
  );
}
export function TabsContent({ className, ...p }: ComponentProps<typeof T.Content>) {
  return <T.Content className={cn("outline-none data-[state=inactive]:hidden", className)} {...p} />;
}
