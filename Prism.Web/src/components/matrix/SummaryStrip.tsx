import { FileText, CheckCircle2, AlertCircle, XCircle } from "lucide-react";
import type { ClaimsSummary } from "@/types/api";
import { cn } from "@/lib/utils";

interface SummaryStripProps {
  summary: ClaimsSummary;
}

function Num({ children }: { children: React.ReactNode }) {
  return <span className="font-mono font-semibold text-ink">{children}</span>;
}

export function SummaryStrip({ summary }: SummaryStripProps) {
  const { total, supported, partiallySupported, notSupported } = summary;
  const sumMismatch = supported + partiallySupported + notSupported !== total;

  const sentences: React.ReactNode[] = [
    <span key="total">
      This paper makes <Num>{total}</Num> {total === 1 ? "empirical claim." : "empirical claims."}
    </span>,
  ];
  if (supported > 0) {
    sentences.push(
      <span key="supported">
        {" "}
        <Num>{supported}</Num> {supported === 1 ? "is" : "are"} supported by the paper&apos;s own evidence.
      </span>
    );
  }
  if (partiallySupported > 0) {
    sentences.push(
      <span key="partial">
        {" "}
        <Num>{partiallySupported}</Num> {partiallySupported === 1 ? "is" : "are"} partially supported.
      </span>
    );
  }
  if (notSupported > 0) {
    sentences.push(
      <span key="refused">
        {" "}
        <Num>{notSupported}</Num>{" "}
        {notSupported === 1
          ? "is refused — the paper asserts it but the evidence does not back it up."
          : "are refused — the paper asserts them but the evidence does not back them up."}
      </span>
    );
  }

  return (
    <div className="space-y-2 md:space-y-4">
      <div className="rounded-xl border border-hairline bg-surface p-3 md:p-5">
        {sumMismatch && (
          <div className="mb-4 rounded-lg border border-refused bg-refused-bg p-3 text-sm text-refused">
            Warning: claim counts do not sum to the total ({supported} + {partiallySupported} + {notSupported} != {total}).
          </div>
        )}

        <div className="flex flex-col md:flex-row items-start justify-between gap-2 md:items-start md:gap-8">
          <div className="flex-1 space-y-1 text-left md:space-y-3">
            <p className="font-sans text-[10px] uppercase tracking-wider text-ink-tertiary md:text-xs">Audit Summary</p>
            <p className="line-clamp-2 font-sans text-xs leading-snug text-ink-secondary md:line-clamp-none md:text-base md:leading-normal">{sentences}</p>
          </div>
          <div className="flex w-full shrink-0 flex-col items-start text-left md:w-auto md:items-end md:border-l md:border-hairline md:pl-8 md:text-right">
            <p className="gradient-brand font-mono text-2xl tabular-nums md:text-4xl">
              {supported} / {total}
            </p>
            <p className="mt-1 font-sans text-xs text-ink-secondary md:text-sm">
              Supported
              {notSupported > 0 && (
                <span className="text-verdict-refused-text"> · {notSupported} refused</span>
              )}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 md:gap-3 lg:grid-cols-4">
        <StatTile
          icon={FileText}
          iconClass="text-verdict-other-icon"
          textClass="text-verdict-other-text"
          label="Claims"
          value={total}
        />
        <StatTile
          icon={CheckCircle2}
          iconClass="text-verdict-supported-icon"
          textClass="text-verdict-supported-text"
          label="Supported"
          value={supported}
        />
        <StatTile
          icon={AlertCircle}
          iconClass="text-verdict-partial-icon"
          textClass="text-verdict-partial-text"
          label="Partially"
          value={partiallySupported}
        />
        <StatTile
          icon={XCircle}
          iconClass="text-verdict-refused-icon"
          textClass="text-verdict-refused-text"
          label="Not Supported"
          value={notSupported}
        />
      </div>
    </div>
  );
}

function StatTile({
  icon: Icon,
  iconClass,
  textClass,
  label,
  value,
}: {
  icon: typeof FileText;
  iconClass: string;
  textClass: string;
  label: string;
  value: number;
}) {
  return (
    <div className="rounded-xl border border-hairline bg-surface p-2 md:p-4">
      <div className="mb-1 flex items-center gap-1.5 md:mb-3 md:gap-2">
        <Icon className={cn("h-3.5 w-3.5 md:h-4 md:w-4", iconClass)} />
        <span className={cn("font-sans text-[10px] uppercase tracking-wider md:text-xs", textClass)}>{label}</span>
      </div>
      <div className="font-mono text-xl tabular-nums text-ink md:text-4xl">{value}</div>
    </div>
  );
}
