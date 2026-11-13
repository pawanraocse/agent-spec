import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

export function Sheet({ open, onOpenChange, title, description, children, width = "w-[520px]" }: {
  open: boolean; onOpenChange: (o: boolean) => void; title: ReactNode; description?: ReactNode; children: ReactNode; width?: string;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[1px]" />
        <Dialog.Content className={cn("fixed right-0 top-0 z-50 flex h-full max-w-[95vw] flex-col border-l border-border bg-background shadow-2xl outline-none", width)}>
          <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
            <div className="min-w-0">
              <Dialog.Title className="truncate text-sm font-semibold">{title}</Dialog.Title>
              {description ? <Dialog.Description className="mt-0.5 text-xs text-muted-foreground">{description}</Dialog.Description> : <Dialog.Description className="sr-only">details</Dialog.Description>}
            </div>
            <Dialog.Close className="rounded p-1 text-muted-foreground hover:bg-muted" aria-label="Close"><X size={16} /></Dialog.Close>
          </div>
          <div className="scrollbar-thin flex-1 overflow-auto px-5 py-4">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
