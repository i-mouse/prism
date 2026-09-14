import { useState } from "react";
import { useMsal } from "@azure/msal-react";
import { InteractionStatus, type RedirectRequest } from "@azure/msal-browser";
import { loginRequest } from "@/lib/msalConfig";
import { useAuth } from "@/lib/AuthContext";
import { useNavigate, useLocation } from "react-router-dom";

export type IdentityProvider = 'google' | 'microsoft' | 'none';

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

export function AuthButtons() {
  const { instance, inProgress } = useMsal();
  const { signInAsGuest } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);

  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/";

  const handleProviderSignIn = async (provider: IdentityProvider) => {
    if (provider === 'none') return;
    setError(null);
    try {
      const providerRequest: RedirectRequest = { ...loginRequest };
      
      if (provider === 'google') {
        providerRequest.domainHint = 'google.com';
      }
      
      await instance.loginRedirect(providerRequest);
    } catch (err) {
      console.error(`${provider} sign-in error:`, err);
      setError("An error occurred during authentication routing. Please try again.");
    }
  };

  const handleGuestSignIn = async () => {
    setError(null);
    try {
      await signInAsGuest();
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError("Failed to sign in as guest.");
    }
  };

  const isInteracting = inProgress !== InteractionStatus.None;

  return (
    <div className="flex flex-col gap-3 w-full">
      {error && (
        <div role="alert" className="text-red-600 text-sm mb-2 px-2 text-center">
          {error}
        </div>
      )}

      <button
        type="button"
        aria-label="Continue with Google"
        onClick={() => handleProviderSignIn('google')}
        disabled={isInteracting}
        className="w-full flex items-center justify-center gap-3 h-11 bg-white rounded-md border border-gray-300 shadow-sm text-gray-700 text-sm font-medium hover:bg-gray-50 hover:border-[#ea580c] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#ea580c] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <GoogleLogo className="w-5 h-5" />
        {isInteracting ? "Redirecting…" : "Continue with Google"}
      </button>

      <button
        type="button"
        aria-label="Continue as guest"
        onClick={handleGuestSignIn}
        disabled={isInteracting}
        className="w-full flex items-center justify-center h-11 bg-transparent rounded-md border border-gray-200 text-gray-700 text-sm font-normal hover:bg-gray-50 hover:text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-gray-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Continue as guest
      </button>
    </div>
  );
}
