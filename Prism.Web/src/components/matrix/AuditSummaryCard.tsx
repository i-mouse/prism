import type { ClaimsSummary } from "@/types/api";

interface AuditSummaryCardProps {
  summary: ClaimsSummary;
}

export function AuditSummaryCard({ summary }: AuditSummaryCardProps) {
  const { total, supported, partiallySupported, notSupported } = summary;

  const supportedPct = total > 0 ? (supported / total) * 100 : 0;
  const partialPct = total > 0 ? (partiallySupported / total) * 100 : 0;
  const notSupportedPct = total > 0 ? (notSupported / total) * 100 : 0;

  return (
    <div className="rounded-xl border border-hairline bg-surface shadow-card p-4 md:p-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        {/* Left: prose summary */}
        <div className="min-w-0">
          <h2 className="font-sans text-base font-semibold text-ink">Audit summary</h2>
          <p className="mt-1 font-sans text-sm text-ink-secondary leading-relaxed">
            This paper makes <span className="font-semibold text-ink">{total}</span> empirical claims.{" "}
            {supported > 0 && (
              <>
                <span className="font-semibold text-ink">{supported}</span>{" "}
                {supported === 1 ? "is" : "are"} supported by the paper&apos;s own evidence,{" "}
              </>
            )}
            {partiallySupported > 0 && (
              <>
                <span className="font-semibold text-ink">{partiallySupported}</span>{" "}
                {partiallySupported === 1 ? "is" : "are"} partially supported{notSupported > 0 ? " and " : "."}
              </>
            )}
            {notSupported > 0 && (
              <>
                <span className="font-semibold text-ink">{notSupported}</span>{" "}
                {notSupported === 1 ? "is" : "are"} missing supporting evidence.
              </>
            )}
          </p>
        </div>

        {/* Right: progress bar + legend */}
        <div className="shrink-0 w-full md:w-64">
          <div className="flex h-1.5 overflow-hidden rounded-full bg-surface-subtle">
            <div
              style={{ width: `${supportedPct}%` }}
              className="bg-verdict-supported-icon transition-all duration-500"
            />
            <div
              style={{ width: `${partialPct}%` }}
              className="bg-verdict-partial-icon transition-all duration-500"
            />
            <div
              style={{ width: `${notSupportedPct}%` }}
              className="bg-verdict-refused-icon transition-all duration-500"
            />
          </div>

          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2">
            {supported > 0 && (
              <span className="flex items-center gap-1.5 font-sans text-xs text-ink-secondary">
                <span className="h-2 w-2 rounded-full bg-verdict-supported-icon shrink-0" />
                {supported} supported
              </span>
            )}
            {partiallySupported > 0 && (
              <span className="flex items-center gap-1.5 font-sans text-xs text-ink-secondary">
                <span className="h-2 w-2 rounded-full bg-verdict-partial-icon shrink-0" />
                {partiallySupported} partial
              </span>
            )}
            {notSupported > 0 && (
              <span className="flex items-center gap-1.5 font-sans text-xs text-ink-secondary">
                <span className="h-2 w-2 rounded-full bg-verdict-refused-icon shrink-0" />
                {notSupported} unsupported
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
