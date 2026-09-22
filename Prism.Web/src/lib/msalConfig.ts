import { PublicClientApplication, type Configuration } from "@azure/msal-browser";

// ---------------------------------------------------------------------------
// Entra External ID (CIAM) configuration.
// Values come from Vite environment variables — populate these in your
// .env.local (for local dev) or via Azure Container Apps environment
// variables (for production) once the manual portal steps are done.
//
//   VITE_AZURE_CLIENT_ID   = the App Registration Client ID
//   VITE_AZURE_AUTHORITY   = https://<tenant-subdomain>.ciamlogin.com/<tenant-id>
//   VITE_AZURE_REDIRECT_URI = http://localhost:5173  (dev)  |  prod URL (prod)
//
// NEVER hard-code real tenant/client IDs here. This file is committed.
// ---------------------------------------------------------------------------

function requireEnv(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(
      `Missing required environment variable ${name}. Set it in .env.local (dev) or the ` +
        `Azure Container Apps environment (prod) — see the comment block above this function.`,
    );
  }
  return value;
}

const clientId = requireEnv("VITE_AZURE_CLIENT_ID", import.meta.env.VITE_AZURE_CLIENT_ID);

const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: requireEnv("VITE_AZURE_AUTHORITY", import.meta.env.VITE_AZURE_AUTHORITY),
    redirectUri: import.meta.env.VITE_AZURE_REDIRECT_URI ?? window.location.origin,
    postLogoutRedirectUri: "/login",
  },
  cache: {
    // sessionStorage: safer than localStorage for SPAs — tokens are scoped to
    // the current tab and cleared when the browser session ends.
    cacheLocation: "sessionStorage",
  },
};

// Scopes requested at sign-in. openid + profile are the standard OIDC scopes
// for a plain sign-in flow. Do NOT add "<clientId>/.default" here — that
// scope shape requests a custom API permission bundle, not basic login, and
// causes AADSTS70011 (invalid scope) against an Entra External ID (CIAM)
// tenant. See the MSAL.js React SPA tutorial for CIAM:
// https://learn.microsoft.com/en-us/entra/external-id/customers/tutorial-single-page-app-react-sign-in-prepare-app
export const loginRequest = {
  scopes: ["openid", "profile"],
};

// Scopes for API access tokens (e.g. the Authorization header sent to
// /api/chats). Unlike loginRequest, this includes "<clientId>/.default" so
// the token carries this app's own API permissions — required by the
// backend's audience check. Used by acquireTokenSilent/acquireTokenRedirect
// in auth.ts, not by the sign-in redirect.
export const apiTokenRequest = {
  scopes: ["openid", "profile", `${clientId}/.default`],
};

export const msalInstance = new PublicClientApplication(msalConfig);
