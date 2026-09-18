import { useMemo, useState, useEffect } from "react";
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

const filterBadgeCount = (claims: ClaimDto[], value: FilterMode) => {
  if (value === "all") return claims.length;
  return claims.filter((c) => displayLabel(c) === value).length;
};

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

  const totalPages = Math.ceil(visibleClaims.length / itemsPerPage);
  const paginatedClaims = visibleClaims.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  return (
    <div className="flex flex-col">
      {/* ── Filter & Sort bar ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          {filterPills.map(({ label, value }) => {
            const count = filterBadgeCount(claims, value);
            const isActive = filter === value;
            return (
              <button
                key={value}
                onClick={() => setFilter(value)}
                className={cn(
                  "flex items-center gap-1.5 rounded-full border px-4 py-1 text-sm font-medium transition-colors",
                  isActive
                    ? "border-slate-800 bg-slate-800 text-white"
                    : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                )}
              >
                {/* Colour dot for status filters */}
                {value !== "all" && (
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full shrink-0",
                      value === "supported"
                        ? "bg-green-500"
                        : value === "partially_supported"
                          ? "bg-orange-500"
                          : "bg-red-500"
                    )}
                  />
                )}
                {label}
                {count > 0 && (
                  <span
                    className={cn(
                      "flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 font-mono text-[10px] font-semibold",
                      isActive
                        ? "bg-white/20 text-white"
                        : "bg-slate-100 text-slate-600"
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
      <div className="flex flex-col border-t border-slate-100">
        {paginatedClaims.length === 0 ? (
          <div className="py-8 text-center font-sans text-sm text-slate-500">
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
        <div className="flex items-center justify-center gap-4 py-4 border-t border-slate-100 bg-white">
          <button
            type="button"
            disabled={currentPage === 1}
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            className="text-sm font-medium text-slate-600 hover:text-slate-900 disabled:opacity-50 disabled:hover:text-slate-600 transition-colors"
          >
            Previous
          </button>
          <span className="text-sm text-slate-500">
            Page {currentPage} of {totalPages}
          </span>
          <button
            type="button"
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            className="text-sm font-medium text-slate-600 hover:text-slate-900 disabled:opacity-50 disabled:hover:text-slate-600 transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
