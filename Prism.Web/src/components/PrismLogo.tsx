import { useId } from "react";
import { cn } from "@/lib/utils";

// A continuous 3D "folded" triangle design with sharp mitered joints and
// multiply-blended shading to create the illusion of overlapping ribbons.
// The triangle uses three distinct segments that meet precisely at the seams.
export function PrismLogo({ className }: { className?: string }) {
  const leftId = useId();
  const rightId = useId();
  const bottomId = useId();
  const shadow1Id = useId();
  const shadow2Id = useId();
  const shadow3Id = useId();

  return (
    <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" className={cn("h-6 w-6", className)}>
      <defs>
        {/* Left segment: pink/magenta (bottom-left) -> yellow/orange (top) */}
        <linearGradient id={leftId} x1="11" y1="72.5" x2="50" y2="5" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#C53381" />
          <stop offset="100%" stopColor="#F3A03B" />
        </linearGradient>
        
        {/* Right segment: yellow/orange (top) -> teal (bottom-right) */}
        <linearGradient id={rightId} x1="50" y1="5" x2="89" y2="72.5" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#F3A03B" />
          <stop offset="100%" stopColor="#4CB6AC" />
        </linearGradient>
        
        {/* Bottom segment: teal (bottom-right) -> pink/magenta (bottom-left) */}
        <linearGradient id={bottomId} x1="89" y1="72.5" x2="11" y2="72.5" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#4CB6AC" />
          <stop offset="100%" stopColor="#C53381" />
        </linearGradient>

        {/* Shadows for the 3D overlapping effect */}
        <linearGradient id={shadow1Id} x1="50" y1="5" x2="30" y2="39" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="rgba(0,0,0,0.25)" />
          <stop offset="100%" stopColor="rgba(0,0,0,0)" />
        </linearGradient>
        <linearGradient id={shadow2Id} x1="11" y1="72.5" x2="45" y2="72.5" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="rgba(0,0,0,0.25)" />
          <stop offset="100%" stopColor="rgba(0,0,0,0)" />
        </linearGradient>
        <linearGradient id={shadow3Id} x1="89" y1="72.5" x2="65" y2="31" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="rgba(0,0,0,0.25)" />
          <stop offset="100%" stopColor="rgba(0,0,0,0)" />
        </linearGradient>
      </defs>

      {/* Left Leg */}
      <polygon points="50,5 11,72.5 38.73,56.5 50,37" fill={`url(#${leftId})`} />
      <polygon points="50,5 11,72.5 38.73,56.5 50,37" fill={`url(#${shadow1Id})`} style={{ mixBlendMode: 'multiply' }} />
      
      {/* Right Leg */}
      <polygon points="50,5 89,72.5 61.27,56.5 50,37" fill={`url(#${rightId})`} />
      <polygon points="50,5 89,72.5 61.27,56.5 50,37" fill={`url(#${shadow3Id})`} style={{ mixBlendMode: 'multiply' }} />
      
      {/* Bottom Leg */}
      <polygon points="11,72.5 89,72.5 61.27,56.5 38.73,56.5" fill={`url(#${bottomId})`} />
      <polygon points="11,72.5 89,72.5 61.27,56.5 38.73,56.5" fill={`url(#${shadow2Id})`} style={{ mixBlendMode: 'multiply' }} />
    </svg>
  );
}
