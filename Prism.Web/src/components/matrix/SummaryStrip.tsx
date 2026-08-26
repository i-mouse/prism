import { FileText, CheckCircle2, AlertCircle, XCircle } from "lucide-react";
import type { ClaimsSummary } from "@/types/api";

interface SummaryStripProps {
  summary: ClaimsSummary;
}

export function SummaryStrip({ summary }: SummaryStripProps) {
  const { total, supported, partiallySupported, notSupported } = summary;
  const sumMismatch = supported + partiallySupported + notSupported !== total;

  const sentences: string[] = [
    total === 1 ? "This paper makes 1 empirical claim." : `This paper makes ${total} empirical claims.`,
  ];
  if (supported > 0) {
    sentences.push(
      supported === 1
        ? "1 is supported by the paper's own evidence."
        : `${supported} are supported by the paper's own evidence.`
    );
  }
  if (partiallySupported > 0) {
    sentences.push(
      partiallySupported === 1 ? "1 is partially supported." : `${partiallySupported} are partially supported.`
    );
  }
  if (notSupported > 0) {
    sentences.push(
      notSupported === 1
        ? "1 is refused — the paper asserts it but the evidence does not back it up."
        : `${notSupported} are refused — the paper asserts them but the evidence does not back them up.`
    );
  }

  return (
    <div className="space-y-4 rounded-lg border border-border bg-surface p-5">
      {sumMismatch && (
        <div className="rounded-lg border border-refused bg-refused-bg p-3 text-sm text-refused">
          Warning: claim counts do not sum to the total ({supported} + {partiallySupported} + {notSupported} ≠ {total}).
        </div>
      )}

      <div className="flex items-start justify-between gap-8">
        <div className="flex-1 space-y-3">
          <p className="text-xs font-semibold uppercase tracking-[0.05em] text-ink-subtle">AUDIT SUMMARY</p>
          <p className="text-base leading-relaxed text-ink">{sentences.join(" ")}</p>
        </div>
        <div className="flex shrink-0 flex-col items-start border-l border-border pl-8">
          <p className="font-display text-3xl font-bold tabular-nums tracking-[-0.03em] text-supported">
            {supported} / {total}
          </p>
          <p className="mt-1 text-sm text-ink-muted">Supported</p>
          {notSupported > 0 && (
            <p className="mt-2 text-sm tabular-nums text-refused">{notSupported} refused</p>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between gap-8 border-t border-border pt-4">
        <SummaryCell icon={FileText} iconClass="bg-surface-sunken text-ink-muted" label="Claims" value={total} />
        <SummaryCell
          icon={CheckCircle2}
          iconClass="bg-supported-bg text-supported"
          label="Supported"
          value={supported}
        />
        <SummaryCell
          icon={AlertCircle}
          iconClass="bg-partial-bg text-partial"
          label="Partially"
          value={partiallySupported}
        />
        <SummaryCell
          icon={XCircle}
          iconClass="bg-refused-bg text-refused"
          label="Not Supported"
          value={notSupported}
        />
      </div>
    </div>
  );
}

function SummaryCell({
  icon: Icon,
  iconClass,
  label,
  value,
}: {
  icon: typeof FileText;
  iconClass: string;
  label: string;
  value: number;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${iconClass}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <div className="text-xs uppercase tracking-[0.05em] text-ink-subtle">{label}</div>
        <div className="font-display text-2xl font-bold tabular-nums text-ink">{value}</div>
      </div>
    </div>
  );
}
