import { useEffect } from "react";

// Shared across every caller so nested/concurrent locks (e.g. the mobile
// sidebar and the chat bottom sheet both open) don't stomp on each other's
// restore value.
let lockCount = 0;
let previousOverflow: string | null = null;

export function useBodyScrollLock(isLocked: boolean) {
  useEffect(() => {
    if (!isLocked) return;

    if (lockCount === 0) {
      previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
    }
    lockCount += 1;

    return () => {
      lockCount = Math.max(0, lockCount - 1);
      if (lockCount === 0) {
        document.body.style.overflow = previousOverflow ?? "";
        previousOverflow = null;
      }
    };
  }, [isLocked]);
}
