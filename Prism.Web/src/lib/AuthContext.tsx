import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { MsalProvider, useMsal } from "@azure/msal-react";
import { InteractionStatus } from "@azure/msal-browser";
import { msalInstance } from "@/lib/msalConfig";
import {
  getCurrentUser,
  signInAsGuest as signInAsGuestRequest,
  signInWithGoogle as signInWithGoogleRequest,
  signOut as signOutRequest,
  acquireAccessToken,
  type User,
} from "@/lib/auth";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  signInWithGoogle: () => Promise<User>;
  signInAsGuest: () => Promise<User>;
  signOut: () => Promise<void>;
  getAccessToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// Inner component: has access to MSAL context via useMsal().
function AuthProviderInner({ children }: { children: ReactNode }) {
  const { instance, inProgress, accounts } = useMsal();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Handle MSAL redirect callback on page load (called once after Google
    // sign-in redirect returns). Then resolve the current user.
    instance
      .handleRedirectPromise()
      .then(() => {
        setUser(getCurrentUser());
      })
      .catch(console.error)
      .finally(() => setIsLoading(false));
  }, [instance]);

  // [nightfix] Keep user state reactive to MSAL accounts and interaction status changes
  useEffect(() => {
    if (inProgress === InteractionStatus.None) {
      const current = getCurrentUser();
      setUser(current);
      setIsLoading(false);
    }
  }, [inProgress, accounts]);

  const signInWithGoogle = useCallback(async () => {
    return signInWithGoogleRequest();
    // Returns a User only if the flow completes without redirect (never in practice);
    // the real resolution happens in handleRedirectPromise above.
  }, []);

  const signInAsGuest = useCallback(async () => {
    const nextUser = await signInAsGuestRequest();
    setUser(nextUser);
    return nextUser;
  }, []);

  const signOut = useCallback(async () => {
    await signOutRequest();
    setUser(null);
  }, []);

  const getAccessToken = useCallback(async () => {
    return acquireAccessToken();
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, signInWithGoogle, signInAsGuest, signOut, getAccessToken }}>
      {children}
    </AuthContext.Provider>
  );
}

// Outer wrapper: provides the MsalProvider so useMsal() works inside.
export function AuthProvider({ children }: { children: ReactNode }) {
  return (
    <MsalProvider instance={msalInstance}>
      <AuthProviderInner>{children}</AuthProviderInner>
    </MsalProvider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
