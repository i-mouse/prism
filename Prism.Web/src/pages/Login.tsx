import { useEffect } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import { useMsal, useIsAuthenticated } from "@azure/msal-react";
import { InteractionStatus } from "@azure/msal-browser";
import { AuthButtons } from "@/components/AuthButtons";

const LANDING_URL = import.meta.env.VITE_LANDING_URL || "/";
const isExternalLanding = LANDING_URL !== "/";

export function Login() {
  const { user, isLoading } = useAuth();
  const { inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const navigate = useNavigate();
  const location = useLocation();

  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/";

  useEffect(() => {
    if (!isLoading && user) {
      navigate(redirectTo, { replace: true });
    }
  }, [isLoading, user, navigate, redirectTo]);

  // [nightfix] Listen to MSAL state and navigate when redirect flow finishes
  useEffect(() => {
    if (isAuthenticated && inProgress === InteractionStatus.None) {
      navigate(redirectTo, { replace: true });
    }
  }, [isAuthenticated, inProgress, navigate, redirectTo]);

  if ((!isLoading && user) || (isAuthenticated && inProgress === InteractionStatus.None)) {
    return null;
  }

  return (
    <div className="relative min-h-dvh w-full flex flex-col font-sans bg-[#F9F9F8] bg-[radial-gradient(#e5e7eb_1px,transparent_1px)] [background-size:16px_16px]">
      
      {/* Top Nav */}
      <header className="flex items-center justify-between px-6 py-6 sm:px-8 w-full max-w-7xl mx-auto">
        {/* Wordmark */}
        <div className="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" className="text-ink">
            <defs>
              <linearGradient id="prism-gradient" x1="0%" y1="100%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#ef4444" />
                <stop offset="50%" stopColor="#f97316" />
                <stop offset="100%" stopColor="#eab308" />
              </linearGradient>
            </defs>
            <polygon points="12 4 4 18 20 18" fill="url(#prism-gradient)" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
          <span className="font-['Georgia','Times_New_Roman',serif] text-ink text-xl tracking-wide font-medium">
            PRISM
          </span>
        </div>

        {/* Secondary Links */}
        <nav className="flex items-center gap-6">
          <a
            href={isExternalLanding ? LANDING_URL : "#"}
            className="text-sm font-medium text-ink-muted hover:text-ink transition-colors"
          >
            Live demo
          </a>
          <a
            href="https://github.com/i-mouse/prism"
            target="_blank"
            rel="noreferrer"
            className="text-sm font-medium text-ink-muted hover:text-ink transition-colors"
          >
            GitHub
          </a>
          <a
            href="#"
            className="text-sm font-medium text-ink-muted hover:text-ink transition-colors"
          >
            Blog
          </a>
        </nav>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-12">
        
        {/* Headline & Tagline */}
        <div className="text-center mb-10 max-w-2xl mx-auto">
          <div className="text-xs font-semibold tracking-[0.2em] text-ink-muted uppercase mb-3">
            Welcome to PRISM
          </div>
          <h1 className="font-['Georgia','Times_New_Roman',serif] text-3xl sm:text-4xl md:text-5xl font-medium text-ink leading-tight mb-4">
            Audit any paper's claims<br />
            against its own evidence
          </h1>
          <p className="text-base text-ink-muted max-w-xl mx-auto leading-relaxed">
            A grounding-checked second opinion on research papers, for reviewers and readers before they cite.
          </p>
        </div>

        {/* Login Card */}
        <div className="w-full max-w-[400px] bg-white rounded-2xl border border-gray-200 shadow-sm p-6 sm:p-8">
          <AuthButtons />
        </div>

        {/* Legal Text */}
        <div className="mt-8 text-center">
          <p className="text-xs text-gray-400">
            By continuing, you agree to the{" "}
            <Link to="/terms" className="hover:text-gray-600 underline underline-offset-2">Terms</Link>
            {" "}and{" "}
            <Link to="/privacy" className="hover:text-gray-600 underline underline-offset-2">Privacy Policy</Link>.
          </p>
        </div>
      </main>
    </div>
  );
}
