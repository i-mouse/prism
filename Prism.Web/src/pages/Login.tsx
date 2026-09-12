import { useEffect } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";

const LANDING_URL = import.meta.env.VITE_LANDING_URL || "/";
const isExternalLanding = LANDING_URL !== "/";

function GoogleLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true">
      <path fill="#4285F4" d="M45.12 24.5c0-1.56-.14-3.06-.4-4.5H24v8.51h11.84c-.51 2.75-2.06 5.08-4.39 6.64v5.52h7.11c4.16-3.83 6.56-9.47 6.56-16.17z" />
      <path fill="#34A853" d="M24 46c5.94 0 10.92-1.97 14.56-5.33l-7.11-5.52c-1.97 1.32-4.49 2.1-7.45 2.1-5.73 0-10.58-3.87-12.31-9.07H4.34v5.7C7.96 41.07 15.4 46 24 46z" />
      <path fill="#FBBC05" d="M11.69 28.18A13.93 13.93 0 0 1 10.9 24c0-1.45.25-2.86.69-4.18v-5.7H4.34A21.93 21.93 0 0 0 2 24c0 3.55.85 6.91 2.34 9.88l7.35-5.7z" />
      <path fill="#EA4335" d="M24 10.75c3.23 0 6.13 1.11 8.41 3.29l6.31-6.31C34.91 4.18 29.93 2 24 2 15.4 2 7.96 6.93 4.34 14.12l7.35 5.7c1.73-5.2 6.58-9.07 12.31-9.07z" />
    </svg>
  );
}

export function Login() {
  const { user, isLoading, signInWithGoogle, signInAsGuest } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/";

  useEffect(() => {
    if (!isLoading && user) {
      navigate(redirectTo, { replace: true });
    }
  }, [isLoading, user, navigate, redirectTo]);

  if (!isLoading && user) {
    return null;
  }

  const handleGoogleSignIn = async () => {
    console.log('TODO: wire in PR 2b');
    await signInWithGoogle();
    navigate(redirectTo, { replace: true });
  };

  const handleGuestSignIn = async () => {
    await signInAsGuest();
    navigate(redirectTo, { replace: true });
  };

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
          
          <div className="flex flex-col gap-3">
            <button
              type="button"
              onClick={handleGoogleSignIn}
              className="w-full flex items-center justify-center gap-3 h-11 bg-white rounded-md border border-gray-300 shadow-sm text-gray-700 text-sm font-medium hover:bg-gray-50 hover:border-[#ea580c] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#ea580c] transition-colors"
            >
              <GoogleLogo className="w-5 h-5" />
              Continue with Google
            </button>

            <button
              type="button"
              onClick={handleGuestSignIn}
              className="w-full flex items-center justify-center h-11 bg-transparent rounded-md border border-gray-200 text-gray-700 text-sm font-normal hover:bg-gray-50 hover:text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-gray-900 transition-colors"
            >
              Continue as guest
            </button>
          </div>
          
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
