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

const sizeClasses = {
  default: "gap-1.5 text-xs px-2.5 py-1",
  // Bumped from text-[11px]: it read too small next to the table's
  // text-[15px] claim copy.
  sm: "gap-1 text-xs px-2.5 py-1",
  xs: "gap-0.5 text-[10px] px-1.5 py-0.5",
} as const;

const iconSizeClasses = {
  default: "h-3 w-3",
  sm: "h-3 w-3",
  xs: "h-2.5 w-2.5",
} as const;

export function VerdictPill({
  verdict,
  label,
  size = "default",
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
        "inline-flex items-center rounded whitespace-nowrap font-bold leading-none",
        sizeClasses[size],
        c.classes,
        className
      )}
    >
      <c.Icon className={cn(iconSizeClasses[size], "stroke-[3]")} />
      {label || c.label}
    </span>
  );
}
