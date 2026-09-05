import { useEffect, useState } from "react";

const STORAGE_KEY = "prism.overviewCollapsed";

// Mobile users need the claim list space more urgently, so the audit
// overview (summary strip + stat tiles) defaults to collapsed there and
// expanded on desktop — but only until the user picks explicitly, at
// which point their choice sticks regardless of viewport.
function getDefaultCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  return !window.matchMedia("(min-width: 1024px)").matches;
}

export function useOverviewCollapsed() {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "true") return true;
    if (stored === "false") return false;
    return getDefaultCollapsed();
  });

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, String(collapsed));
  }, [collapsed]);

  return [collapsed, setCollapsed] as const;
}
