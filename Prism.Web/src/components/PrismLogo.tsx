import { useId } from "react";
import { cn } from "@/lib/utils";

export function PrismLogo({ className }: { className?: string }) {
  const maskId = useId();
  const topGrad = useId();
  const leftGrad = useId();
  const rightGrad = useId();

  return (
    <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" className={cn("h-6 w-6", className)}>
      <defs>
        <mask id={maskId}>
          <path
            d="M 50 16 L 86 84 L 14 84 Z"
            fill="none"
            stroke="white"
            strokeWidth="14"
            strokeLinejoin="miter"
            strokeMiterlimit="3"
          />
        </mask>
        <radialGradient id={topGrad} cx="50%" cy="16%" r="75%">
          <stop offset="0%" stopColor="#0f172a" />
          <stop offset="100%" stopColor="#0f172a" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={leftGrad} cx="14%" cy="84%" r="75%">
          <stop offset="0%" stopColor="#6366f1" />
          <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={rightGrad} cx="86%" cy="84%" r="75%">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#38bdf8" stopOpacity="0" />
        </radialGradient>
      </defs>
      <g mask={`url(#${maskId})`}>
        <rect x="0" y="0" width="100" height="100" fill="#0f172a" />
        <rect x="0" y="0" width="100" height="100" fill={`url(#${leftGrad})`} />
        <rect x="0" y="0" width="100" height="100" fill={`url(#${rightGrad})`} />
        <rect x="0" y="0" width="100" height="100" fill={`url(#${topGrad})`} />
      </g>
    </svg>
  );
}
