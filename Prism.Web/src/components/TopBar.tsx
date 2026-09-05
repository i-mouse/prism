import { ChevronDown, Menu } from "lucide-react";
import { PrismLogo } from "@/components/PrismLogo";
import { Link } from "react-router-dom";

export function TopBar({ onMenuClick }: { onMenuClick?: () => void }) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-hairline bg-surface px-4 md:px-6 py-3">
      <div className="flex items-center gap-2">
        <button onClick={onMenuClick} className="mr-2 lg:hidden text-ink-secondary hover:text-ink">
          <Menu className="h-6 w-6" />
        </button>
        <Link to="/" className="flex items-center gap-2" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
          <PrismLogo className="h-6 w-6" />
          <span className="font-sans font-semibold text-ink">Prism</span>
        </Link>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-subtle text-sm font-medium text-ink">
          N
        </div>
        <div className="flex items-center gap-1 cursor-pointer">
          <span className="text-sm text-ink hidden md:inline">Nitin</span>
          <ChevronDown className="h-4 w-4 text-ink-tertiary" />
        </div>
      </div>
    </header>
  );
}
