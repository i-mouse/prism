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

debugger;
const msalConfig: Configuration = {
  auth: {
    clientId: import.meta.env.VITE_AZURE_CLIENT_ID ?? "PLACEHOLDER_CLIENT_ID",
    authority: import.meta.env.VITE_AZURE_AUTHORITY ?? "https://login.microsoftonline.com/PLACEHOLDER_TENANT_ID",
    redirectUri: import.meta.env.VITE_AZURE_REDIRECT_URI ?? window.location.origin,
    postLogoutRedirectUri: "/login",
  },
  cache: {
    // sessionStorage: safer than localStorage for SPAs — tokens are scoped to
    // the current tab and cleared when the browser session ends.
    cacheLocation: "sessionStorage",
  },
};

// Scopes the SPA requests in the access token — must match the API's audience.
// For Entra External ID the default scope is openid + the API scope defined
// in the App Registration. Adjust "api://<clientId>/access" once the scope is
// created in the portal.
export const loginRequest = {
  scopes: [
    "openid",
    "profile",
    `${import.meta.env.VITE_AZURE_CLIENT_ID ?? "PLACEHOLDER_CLIENT_ID"}/.default`,
  ],
};

export const msalInstance = new PublicClientApplication(msalConfig);
