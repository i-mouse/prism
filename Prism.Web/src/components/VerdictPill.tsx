import { Check, Minus, X, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

export type Verdict = "supported" | "partial" | "refused" | "other";

const config = {
  supported: {
    label: "SUPPORTED",
    Icon: Check,
    classes: "bg-green-100 text-green-700",
    iconContainerClass: "bg-green-700",
  },
  partial: {
    label: "PARTIALLY SUPPORTED",
    Icon: Minus,
    classes: "bg-orange-100 text-orange-700",
    iconContainerClass: "bg-orange-700",
  },
  refused: {
    label: "NOT SUPPORTED",
    Icon: X,
    classes: "bg-red-100 text-red-700",
    iconContainerClass: "bg-red-700",
  },
  other: {
    label: "OTHER",
    Icon: AlertTriangle,
    classes: "bg-slate-100 text-slate-700",
    iconContainerClass: "bg-slate-700",
  },
} as const;

export const verdictBorderClass: Record<Verdict, string> = {
  supported: "bg-green-200",
  partial: "bg-orange-200",
  refused: "bg-red-200",
  other: "bg-slate-200",
};

export function VerdictPill({
  verdict,
  label,
  className,
}: {
  verdict: Verdict;
  label?: string;
  size?: "default" | "sm" | "xs";
  className?: string;
}) {
  const c = config[verdict];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full whitespace-nowrap text-xs font-bold px-2.5 py-1",
        c.classes,
        className
      )}
    >
      <c.Icon className="h-3 w-3 stroke-[3]" />
      {label || c.label}
    </span>
  );
}
