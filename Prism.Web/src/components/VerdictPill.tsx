import { Check, AlertTriangle, X } from "lucide-react";
import { cn } from "@/lib/utils";

export type Verdict = "supported" | "partial" | "refused" | "other";

const config = {
  supported: {
    label: "SUPPORTED",
    Icon: Check,
    classes: "bg-verdict-supported-bg text-verdict-supported-text",
    iconClass: "text-verdict-supported-icon",
  },
  partial: {
    label: "PARTIAL",
    Icon: AlertTriangle,
    classes: "bg-verdict-partial-bg text-verdict-partial-text",
    iconClass: "text-verdict-partial-icon",
  },
  refused: {
    label: "NOT SUPPORTED",
    Icon: X,
    classes: "bg-verdict-refused-bg text-verdict-refused-text",
    iconClass: "text-verdict-refused-icon",
  },
  other: {
    label: "OTHER",
    Icon: AlertTriangle,
    classes: "bg-verdict-other-bg text-verdict-other-text",
    iconClass: "text-verdict-other-icon",
  },
} as const;

// Literal per-verdict class names — Tailwind's scanner only picks up
// string literals, so this can't be built with template interpolation.
export const verdictBorderClass: Record<Verdict, string> = {
  supported: "bg-verdict-supported-border",
  partial: "bg-verdict-partial-border",
  refused: "bg-verdict-refused-border",
  other: "bg-verdict-other-border",
};

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
        "inline-flex items-center gap-1 rounded-full font-mono uppercase tracking-wider",
        size === "default" && "gap-1.5 px-2.5 py-1 text-xs",
        size === "sm" && "gap-1.5 px-2 py-0.5 text-[10px]",
        size === "xs" && "px-1.5 py-0.5 text-[9px]",
        c.classes,
        className
      )}
    >
      <c.Icon className={cn(size === "xs" ? "h-2.5 w-2.5" : "h-3 w-3", c.iconClass)} strokeWidth={2.5} />
      {label ?? c.label}
    </span>
  );
}
