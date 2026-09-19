import { useMemo, useState, useEffect } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { ClaimDto, ClaimLabel } from "@/types/api";
import { ClaimTableRow } from "@/components/matrix/ClaimTableRow";
import { AbsenceRow } from "@/components/matrix/AbsenceRow";
import { displayLabel } from "@/lib/claim-display";
import { cn } from "@/lib/utils";

interface ClaimListProps {
  claims: ClaimDto[];
  onViewEvidence: (claimId: string) => void;
  sortControl?: React.ReactNode;
}

type FilterMode = "all" | ClaimLabel;

const filterPills: { label: string; value: FilterMode }[] = [
  { label: "All", value: "all" },
  { label: "Supported", value: "supported" },
  { label: "Partially Supported", value: "partially_supported" },
  { label: "Not Supported", value: "not_supported" },
];

const filterDotClass: Record<Exclude<FilterMode, "all">, string> = {
  supported: "bg-verdict-supported-icon",
  partially_supported: "bg-verdict-partial-icon",
  not_supported: "bg-verdict-refused-icon",
};

const filterBadgeCount = (claims: ClaimDto[], value: FilterMode) => {
  if (value === "all") return claims.length;
  return claims.filter((c) => displayLabel(c) === value).length;
};

// Builds a compact page list with ellipsis gaps, e.g. [1, "…", 4, 5, 6, "…", 12].
function buildPageList(current: number, total: number): (number | "ellipsis")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);

  const pages = new Set([1, total, current - 1, current, current + 1]);
  const sorted = [...pages].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);

  const result: (number | "ellipsis")[] = [];
  let prev = 0;
  for (const p of sorted) {
    if (prev && p - prev > 1) result.push("ellipsis");
    result.push(p);
    prev = p;
  }
  return result;
}

export function ClaimList({ claims, onViewEvidence, sortControl }: ClaimListProps) {
  const [filter, setFilter] = useState<FilterMode>("all");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 15;

  const visibleClaims = useMemo(() => {
    if (filter === "all") return claims;
    return claims.filter((c) => displayLabel(c) === filter);
  }, [claims, filter]);

  // Reset page when filter changes
  useEffect(() => {
    setCurrentPage(1);
  }, [filter]);

  const totalPages = Math.max(1, Math.ceil(visibleClaims.length / itemsPerPage));
  // Defensive clamp: guards against a stale currentPage briefly outliving a
  // shrunken claim list (e.g. a filter change firing before its own reset
  // effect above runs) rather than slicing into an out-of-range page.
  const safePage = Math.min(currentPage, totalPages);
  const paginatedClaims = visibleClaims.slice(
    (safePage - 1) * itemsPerPage,
    safePage * itemsPerPage
  );

  return (
    <div className="flex flex-col">
      {/* ── Filter & Sort bar ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 border-b border-hairline">
        <div className="flex flex-wrap items-center gap-2">
          {filterPills.map(({ label, value }) => {
            const count = filterBadgeCount(claims, value);
            const isActive = filter === value;
            return (
              <button
                key={value}
                onClick={() => setFilter(value)}
                className={cn(
                  "flex items-center gap-1.5 rounded-md border px-4 py-1 text-sm font-medium transition-colors",
                  isActive
                    ? "border-ink bg-ink text-white"
                    : "border-hairline bg-surface text-ink-secondary hover:border-border-strong hover:bg-surface-subtle hover:text-ink"
                )}
              >
                {/* Colour dot for status filters */}
                {value !== "all" && (
                  <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", filterDotClass[value])} />
                )}
                {label}
                {count > 0 && (
                  <span
                    className={cn(
                      "flex h-5 min-w-5 items-center justify-center rounded px-1.5 font-mono text-[10px] font-semibold",
                      isActive ? "bg-white/20 text-white" : "bg-surface-muted text-ink-tertiary"
                    )}
                  >
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {sortControl && (
          <div className="flex shrink-0">
            {sortControl}
          </div>
        )}
      </div>

      {/* ── Claims list ── */}
      <div className="flex flex-col">
        {/* Table Header */}
        <div className="grid grid-cols-[minmax(0,1fr)_190px_140px] gap-6 items-center px-4 py-2.5 border-b border-hairline bg-surface-subtle/60">
          <div className="font-sans text-xs font-semibold text-ink-tertiary uppercase tracking-wider">Claim</div>
          <div className="font-sans text-xs font-semibold text-ink-tertiary uppercase tracking-wider">Status</div>
          <div className="font-sans text-xs font-semibold text-ink-tertiary uppercase tracking-wider text-right pr-4">Action</div>
        </div>

        {paginatedClaims.length === 0 ? (
          <div className="py-8 text-center font-sans text-sm text-ink-tertiary">
            No claims match this filter.
          </div>
        ) : (
          paginatedClaims.map((claim) =>
            claim.missing ? (
              <AbsenceRow
                key={claim.id}
                claim={claim}
                onViewEvidence={() => onViewEvidence(claim.id)}
              />
            ) : (
              <ClaimTableRow
                key={claim.id}
                claim={claim}
                onViewEvidence={() => onViewEvidence(claim.id)}
              />
            )
          )
        )}
      </div>

      {/* ── Pagination Footer ── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1.5 py-4 border-t border-hairline bg-surface">
          <button
            type="button"
            aria-label="Previous page"
            disabled={safePage === 1}
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            className="flex h-8 w-8 items-center justify-center rounded-md text-ink-secondary transition-colors hover:bg-surface-subtle hover:text-ink disabled:opacity-40 disabled:hover:bg-transparent"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>

          {buildPageList(safePage, totalPages).map((p, idx) =>
            p === "ellipsis" ? (
              <span key={`ellipsis-${idx}`} className="px-1.5 font-sans text-sm text-ink-tertiary select-none">
                …
              </span>
            ) : (
              <button
                key={p}
                type="button"
                onClick={() => setCurrentPage(p)}
                aria-current={p === safePage ? "page" : undefined}
                className={cn(
                  "flex h-8 min-w-8 items-center justify-center rounded-md px-2 font-sans text-sm font-medium transition-colors",
                  p === safePage
                    ? "bg-ink text-white"
                    : "text-ink-secondary hover:bg-surface-subtle hover:text-ink"
                )}
              >
                {p}
              </button>
            )
          )}

          <button
            type="button"
            aria-label="Next page"
            disabled={safePage === totalPages}
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            className="flex h-8 w-8 items-center justify-center rounded-md text-ink-secondary transition-colors hover:bg-surface-subtle hover:text-ink disabled:opacity-40 disabled:hover:bg-transparent"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
