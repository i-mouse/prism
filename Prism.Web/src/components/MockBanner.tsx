import { useMockStatus } from "@/hooks/useMockStatus";

export function MockBanner() {
  const { enabled } = useMockStatus();

  if (!enabled) return null;

  return (
    <div className="sticky top-0 z-30 flex items-center justify-center gap-3 border-b border-purple-200 bg-purple-50 px-4 py-2">
      <p className="font-sans text-sm text-purple-900 font-medium">
        🧪 Mock Mode — this paper's claims are simulated, not a real audit
      </p>
    </div>
  );
}
