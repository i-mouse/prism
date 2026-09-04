import { useId } from "react";
import { cn } from "@/lib/utils";

export function PrismLogo({ className }: { className?: string }) {
  const gradientId = useId();

  return (
    <svg
      viewBox="0 0 100 100"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("h-6 w-6", className)}
    >
      <defs>
        <linearGradient id={gradientId} x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#ec4899" />
          <stop offset="50%" stopColor="#f97316" />
          <stop offset="100%" stopColor="#fbbf24" />
        </linearGradient>
      </defs>
      <path
        d="M 50 15 L 85 85 L 15 85 Z"
        fill="none"
        stroke={`url(#${gradientId})`}
        strokeWidth="14"
        strokeLinejoin="round"
      />
    </svg>
  );
}
