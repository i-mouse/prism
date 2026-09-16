import { msalInstance, loginRequest } from "@/lib/msalConfig";
import type { AccountInfo } from "@azure/msal-browser";

export type AuthProvider = "google" | "guest";

export interface User {
  id: string;
  email: string | null;
  name: string | null;
  provider: AuthProvider;
}

export interface AuthState {
  user: User | null;
  isLoading: boolean;
}

// Key retained for backward-compat reads — see AuthContext.tsx bootstrap.
const STORAGE_KEY = "prism.auth.user";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function accountToUser(account: AccountInfo): User {
  const rawName = account.name;
  const name = (!rawName || rawName === "unknown") ? "Google User" : rawName;

  return {
    // MSAL surfaces the OID (object ID) as account.homeAccountId; for a
    // simpler, stable identifier we use account.localAccountId which matches
    // the Entra "oid" claim that the API can look up.
    id: account.localAccountId,
    email: account.username ?? null,
    name,
    provider: "google",
  };
}

function persistUser(user: User) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(user));
}

function clearPersistedUser() {
  sessionStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(STORAGE_KEY); // clean up old localStorage key if present
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Returns the currently signed-in user from MSAL (Google) or the guest state
 * persisted in sessionStorage. Returns null if the user is not authenticated.
 */
export function getCurrentUser(): User | null {
  // 1. Check MSAL for an active Google-authenticated account.
  const accounts = msalInstance.getAllAccounts();
  if (accounts.length > 0) {
    return accountToUser(accounts[0]);
  }

  // 2. Fall back to the persisted guest state.
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY) ?? localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as User;
      if (parsed.provider === "guest") return parsed;
    }
  } catch {
    // ignore parse errors
  }

  return null;
}

/**
 * Acquires an access token silently for the active Google account.
 * Returns null if the user is not Google-authenticated.
 */
export async function acquireAccessToken(): Promise<string | null> {
  const accounts = msalInstance.getAllAccounts();
  if (accounts.length === 0) return null;

  try {
    const result = await msalInstance.acquireTokenSilent({
      ...loginRequest,
      account: accounts[0],
    });
    return result.accessToken;
  } catch {
    // Token refresh failed — let MSAL redirect to re-authenticate.
    await msalInstance.acquireTokenRedirect({ ...loginRequest, account: accounts[0] });
    return null;
  }
}

/**
 * Initiates the Entra External ID / Google PKCE redirect flow.
 * The page navigates away — the returned promise resolves only after the
 * user is redirected back and MSAL processes the callback.
 */
export async function signInWithGoogle(): Promise<User> {
  await msalInstance.loginRedirect(loginRequest);
  // This line is never reached in the same navigation — MSAL redirects.
  // The AuthContext bootstrap reads the account on the post-redirect page load.
  throw new Error("Unreachable after redirect");
}

/**
 * Calls the backend to create a server-generated guest session cookie (HttpOnly).
 * The response does not include the session ID — it lives only in the cookie.
 */
export async function signInAsGuest(): Promise<User> {
  const res = await fetch("/api/auth/guest", { method: "POST", credentials: "include" });
  if (!res.ok) {
    throw new Error(`Guest sign-in failed: ${res.statusText}`);
  }

  // We do not know the session ID (it is HttpOnly). The frontend state tracks
  // only that the user is a guest; the ID is resolved server-side on every request.
  const user: User = {
    id: "guest", // opaque placeholder; backend never trusts this value
    email: null,
    name: "Guest",
    provider: "guest",
  };
  persistUser(user);
  return user;
}

/**
 * Signs out the current user.
 * Google-authenticated: MSAL redirect logout + server cookie clear.
 * Guest: server cookie clear + local state clear.
 */
export async function signOut(): Promise<void> {
  clearPersistedUser();

  // Always clear the server-side guest cookie, harmless for Google users.
  await fetch("/api/auth/logout", { method: "POST", credentials: "include" }).catch(() => {});

  const accounts = msalInstance.getAllAccounts();
  if (accounts.length > 0) {
    await msalInstance.logoutRedirect({
      account: accounts[0],
      postLogoutRedirectUri: "/login",
    });
    // Page navigates away; code below does not run.
  }
}
