import { ChevronDown } from "lucide-react";
import { PrismLogo } from "@/components/PrismLogo";

export function TopBar() {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-hairline bg-surface px-6 py-3">
      <div className="flex items-center gap-2">
        <PrismLogo className="h-6 w-6" />
        <span className="font-sans font-semibold text-ink">Prism</span>
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
