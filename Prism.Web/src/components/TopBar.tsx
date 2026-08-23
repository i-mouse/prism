import { Sparkles, ChevronDown } from "lucide-react";

export function TopBar() {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-surface px-6">
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-ink" />
        <span className="font-display text-sm font-semibold tracking-tight text-ink">
          Prism Audit Console
        </span>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-sunken text-sm font-medium text-ink">
          N
        </div>
        <div className="flex items-center gap-1">
          <span className="text-sm text-ink">Nitin</span>
          <ChevronDown className="h-4 w-4 text-ink-muted" />
        </div>
      </div>
    </header>
  );
}
