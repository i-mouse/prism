import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { motion, useMotionValue, animate } from "framer-motion";
import { useBodyScrollLock } from "@/hooks/useBodyScrollLock";

export type SheetState = "peek" | "half" | "full";

const TOP_NAV_HEIGHT = 56; // px — matches TopBar's h-14
const HALF_FRACTION = 0.5;
const FULL_FRACTION = 0.95;
const DEFAULT_PEEK_PX = 96; // fallback before the peek content's real height is measured
const EASE: [number, number, number, number] = [0.32, 0.72, 0, 1];
const DURATION = 0.25;
const VELOCITY_THRESHOLD = 500; // px/s — fast swipes jump a state regardless of position
const TAP_THRESHOLD_PX = 5; // movement under this counts as a tap, not a drag
const STATE_ORDER: SheetState[] = ["peek", "half", "full"];

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// visualViewport tracks the actual visible viewport (shrinks for the
// on-screen keyboard or mobile browser chrome) far more reliably than
// window.innerHeight, which many mobile browsers report as the LARGEST
// possible viewport regardless of URL-bar state — the root cause of the
// bottom sheet getting cut off on iOS/Android.
function getViewportHeight() {
  if (typeof window === "undefined") return 0;
  return window.visualViewport?.height ?? window.innerHeight;
}

interface DragState {
  startY: number;
  startHeight: number;
  lastY: number;
  lastT: number;
  velocity: number;
}

export function ChatBottomSheet({
  state,
  onStateChange,
  bottomContent,
  children,
}: {
  state: SheetState;
  onStateChange: (state: SheetState) => void;
  /** Chips + input — rendered at the bottom of the sheet in every state. Its
   *  natural height is measured and used as the "peek" snap point. */
  bottomContent: ReactNode;
  /** Message list — fills the space above bottomContent; naturally collapses
   *  to ~0 height at "peek" since there's no room left for it there. */
  children: ReactNode;
}) {
  useBodyScrollLock(state !== "peek");
  const bottomRef = useRef<HTMLDivElement>(null);
  const [peekPx, setPeekPx] = useState(DEFAULT_PEEK_PX);

  // Re-measures after every render (not just mount) since bottomContent's
  // natural height changes whenever the suggested-chip row shows/hides —
  // a plain re-render, not a ResizeObserver-worthy size change on its own.
  // ResizeObserver is kept too for cases a render alone won't catch (the
  // textarea auto-growing as the user types, mutating the DOM directly).
  useLayoutEffect(() => {
    const el = bottomRef.current;
    if (!el) return;
    // Add 22px to account for the drag handle's height (pt-2.5 + pb-2 + h-1 = 10+8+4)
    const measure = () => setPeekPx((el.getBoundingClientRect().height || DEFAULT_PEEK_PX) + 22);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  });

  const heightFor = (s: SheetState) => {
    if (s === "full") return getViewportHeight() * FULL_FRACTION - TOP_NAV_HEIGHT;
    if (s === "half") return getViewportHeight() * HALF_FRACTION;
    // peekPx is measured off the real bottomContent DOM node, which already
    // includes its own safe-area-inset-bottom padding — no need to add it twice.
    return peekPx;
  };

  const height = useMotionValue(heightFor(state));
  const dragRef = useRef<DragState | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const prevStateRef = useRef(state);

  useEffect(() => {
    if (isDragging) return;
    const target = heightFor(state);
    const isGenuineStateChange = prevStateRef.current !== state;
    prevStateRef.current = state;

    // A peekPx correction (the chip row showing/hiding, or the initial
    // measurement replacing the DEFAULT_PEEK_PX guess) while already sitting
    // at "peek" isn't a user-triggered transition — apply it immediately
    // rather than animating, so it doesn't depend on an animation frame
    // completing to reach the correct, on-screen height.
    if (!isGenuineStateChange) {
      height.set(target);
      return;
    }

    const controls = animate(height, target, prefersReducedMotion() ? { duration: 0 } : { duration: DURATION, ease: EASE });
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, isDragging, peekPx]);

  useEffect(() => {
    const recompute = () => {
      if (!isDragging) height.set(heightFor(state));
    };
    window.addEventListener("resize", recompute);
    window.visualViewport?.addEventListener("resize", recompute);
    return () => {
      window.removeEventListener("resize", recompute);
      window.visualViewport?.removeEventListener("resize", recompute);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, isDragging, peekPx]);

  const nearestState = (currentHeight: number, velocity: number): SheetState => {
    const idx = STATE_ORDER.indexOf(state);
    if (velocity < -VELOCITY_THRESHOLD && idx < STATE_ORDER.length - 1) return STATE_ORDER[idx + 1]; // fast drag up -> expand
    if (velocity > VELOCITY_THRESHOLD && idx > 0) return STATE_ORDER[idx - 1]; // fast drag down -> collapse

    let closest: SheetState = "peek";
    let bestDist = Infinity;
    for (const candidate of STATE_ORDER) {
      const dist = Math.abs(heightFor(candidate) - currentHeight);
      if (dist < bestDist) {
        bestDist = dist;
        closest = candidate;
      }
    }
    return closest;
  };

  const handlePointerDown = (e: React.PointerEvent) => {
    dragRef.current = { startY: e.clientY, startHeight: height.get(), lastY: e.clientY, lastT: performance.now(), velocity: 0 };
    setIsDragging(true);
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    const now = performance.now();
    const dt = now - drag.lastT;
    if (dt > 0) drag.velocity = ((e.clientY - drag.lastY) / dt) * 1000;
    drag.lastY = e.clientY;
    drag.lastT = now;

    // Dragging the handle UP (clientY decreasing) grows the sheet.
    const delta = drag.startY - e.clientY;
    const min = peekPx;
    const max = heightFor("full");
    height.set(Math.min(max, Math.max(min, drag.startHeight + delta)));
  };

  const endDrag = () => {
    const drag = dragRef.current;
    if (!drag) return;
    const moved = Math.abs(height.get() - drag.startHeight);
    dragRef.current = null;
    setIsDragging(false);

    if (moved < TAP_THRESHOLD_PX) {
      // A tap on the handle advances to the next state instead of snapping
      // back to the same one (which the distance-based logic would do).
      const idx = STATE_ORDER.indexOf(state);
      onStateChange(STATE_ORDER[Math.min(idx + 1, STATE_ORDER.length - 1)]);
      return;
    }
    onStateChange(nearestState(height.get(), drag.velocity));
  };

  return createPortal(
    <>
      {state === "full" && (
        <div className="fixed inset-0 z-40 bg-ink/40 lg:hidden" onClick={() => onStateChange("half")} />
      )}
      <motion.div
        style={{ height }}
        className="fixed inset-x-0 bottom-0 z-50 flex flex-col overflow-hidden rounded-t-2xl border-t border-hairline bg-surface shadow-drawer lg:hidden"
      >
        <div
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          role="button"
          tabIndex={0}
          aria-label="Resize chat sheet"
          className="flex shrink-0 touch-none justify-center pb-2 pt-2.5"
        >
          <div className="h-1 w-4 rounded-full bg-hairline" />
        </div>
        <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
        <div ref={bottomRef} className="shrink-0">
          {bottomContent}
        </div>
      </motion.div>
    </>,
    document.body
  );
}
