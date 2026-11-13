import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

const badgeVariants = cva("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ring-1 ring-inset", {
  variants: {
    tone: {
      neutral: "bg-muted text-muted-foreground ring-border",
      primary: "bg-primary/10 text-primary ring-primary/30",
      success: "bg-success/10 text-success ring-success/30",
      warning: "bg-warning/10 text-warning ring-warning/30",
      danger: "bg-danger/10 text-danger ring-danger/30",
      accent: "bg-accent/10 text-accent ring-accent/30",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export function Badge({ className, tone, ...props }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
