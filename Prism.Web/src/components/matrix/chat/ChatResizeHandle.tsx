import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { MIN_CHAT_HEIGHT, clampChatHeight, getMaxChatHeight } from "@/components/matrix/chat/chatHeight";

const SNAP_FRACTIONS = [0.25, 0.5, 0.75];
const STEP_PX = 10;

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function ChatResizeHandle({
  panelRef,
  height,
  onHeightChange,
}: {
  panelRef: React.RefObject<HTMLDivElement | null>;
  height: number;
  onHeightChange: (height: number) => void;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef({ startY: 0, startHeight: height, raf: null as number | null, pending: null as number | null });
  const previousFocusRef = useRef<HTMLElement | null>(null);

  const applyHeight = useCallback(
    (h: number) => {
      const panel = panelRef.current;
      if (panel) panel.style.height = `${h}px`;
    },
    [panelRef]
  );

  const flushPending = useCallback(() => {
    const state = dragRef.current;
    state.raf = null;
    if (state.pending != null) applyHeight(state.pending);
  }, [applyHeight]);

  const scheduleHeight = useCallback(
    (h: number) => {
      const state = dragRef.current;
      state.pending = h;
      if (state.raf == null) state.raf = requestAnimationFrame(flushPending);
    },
    [flushPending]
  );

  useEffect(() => {
    if (!isDragging) return;

    const handleMove = (e: PointerEvent) => {
      const state = dragRef.current;
      const delta = state.startY - e.clientY; // dragging up increases height
      scheduleHeight(clampChatHeight(state.startHeight + delta));
    };

    const handleUp = (e: PointerEvent) => {
      const state = dragRef.current;
      const delta = state.startY - e.clientY;
      const finalHeight = clampChatHeight(state.startHeight + delta);
      if (state.raf != null) {
        cancelAnimationFrame(state.raf);
        state.raf = null;
      }
      applyHeight(finalHeight);
      setIsDragging(false);
      document.body.classList.remove("is-resizing");
      onHeightChange(finalHeight);
    };

    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
    };
  }, [isDragging, applyHeight, scheduleHeight, onHeightChange]);

  const handlePointerDown = (e: React.PointerEvent) => {
    e.preventDefault();
    dragRef.current.startY = e.clientY;
    dragRef.current.startHeight = height;
    setIsDragging(true);
    document.body.classList.add("is-resizing");
  };

  const handleDoubleClick = () => {
    const vh = window.innerHeight;
    const current = panelRef.current?.getBoundingClientRect().height ?? height;
    const presets = SNAP_FRACTIONS.map((f) => vh * f);
    const nearest = presets.reduce((best, p) => (Math.abs(p - current) < Math.abs(best - current) ? p : best), presets[0]);
    const clamped = clampChatHeight(nearest);
    const panel = panelRef.current;
    if (panel) {
      if (!prefersReducedMotion()) {
        panel.style.transition = "height 200ms cubic-bezier(0.32, 0.72, 0, 1)";
        window.setTimeout(() => {
          panel.style.transition = "";
        }, 220);
      }
      panel.style.height = `${clamped}px`;
    }
    onHeightChange(clamped);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      const next = clampChatHeight(height + (e.key === "ArrowUp" ? STEP_PX : -STEP_PX));
      applyHeight(next);
      onHeightChange(next);
    } else if (e.key === "Escape") {
      previousFocusRef.current?.focus();
    }
  };

  const handleFocus = () => {
    previousFocusRef.current = (document.activeElement as HTMLElement) ?? null;
  };

  return (
    <div
      role="slider"
      tabIndex={0}
      aria-label="Resize chat panel"
      aria-valuemin={MIN_CHAT_HEIGHT}
      aria-valuemax={Math.round(getMaxChatHeight())}
      aria-valuenow={Math.round(height)}
      aria-orientation="horizontal"
      onPointerDown={handlePointerDown}
      onDoubleClick={handleDoubleClick}
      onKeyDown={handleKeyDown}
      onFocus={handleFocus}
      className="group/handle relative hidden h-2 w-full shrink-0 cursor-ns-resize items-center justify-center py-[3.5px] focus:outline-none lg:flex"
    >
      <div
        className={cn(
          "h-0.5 w-full rounded-full bg-hairline transition-all",
          "group-hover/handle:h-1 group-hover/handle:bg-brand",
          "group-focus-visible/handle:h-1 group-focus-visible/handle:bg-brand"
        )}
      />
    </div>
  );
}
