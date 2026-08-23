import { FileSearch } from "lucide-react";

export function DrawerEmptyState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
      <FileSearch className="h-12 w-12 text-ink-subtle" />
      <p className="text-sm text-ink-muted">Select a claim to view its evidence.</p>
    </div>
  );
}
