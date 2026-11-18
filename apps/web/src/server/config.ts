/** Server-side settings from the environment. Nothing secret has a default in code. */

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

/** APP_ENV must be set. Anything other than dev or test gets production rules (fail closed). */
export const appEnv = () => required("APP_ENV");
export const isProductionLike = () => !["dev", "test"].includes(process.env.APP_ENV ?? "");

/**
 * This environment's own address (sign-in redirects, the launch QR code). Dev and test fall back to the local
 * stack; anywhere else it must be set, or every phone that scans the launch QR would open localhost (review A1).
 */
export function appBaseUrl(): URL {
  const value = process.env.APP_BASE_URL;
  if (!value) {
    if (isProductionLike()) throw new Error("APP_BASE_URL is not set");
    return new URL("http://localhost:3000");
  }
  return new URL(value);
}

export function sessionSecret(): string {
  const value = required("SESSION_SECRET");
  if (isProductionLike() && (value.startsWith("change-me") || value.length < 32)) {
    throw new Error("SESSION_SECRET is a placeholder or too short for this environment");
  }
  return value;
}

export function privacyNoticeVersion(): string {
  return required("PRIVACY_NOTICE_VERSION");
}

export type OidcMode = "mock" | "entra";

export function oidcConfig() {
  const mode = required("OIDC_MODE") as OidcMode;
  if (mode !== "mock" && mode !== "entra") throw new Error("OIDC_MODE must be mock or entra");
  if (mode === "mock" && isProductionLike()) throw new Error("OIDC_MODE=mock is not allowed in UAT or prod");
  if (process.env.OIDC_INTERNAL_BASE && isProductionLike()) {
    throw new Error("OIDC_INTERNAL_BASE is a dev-only setting and is refused in UAT and prod");
  }
  return {
    mode,
    issuer: required("OIDC_ISSUER").replace(/\/$/, ""),
    // Dev only: where the server reaches the mock IdP inside Docker (the browser uses OIDC_ISSUER).
    internalBase: process.env.OIDC_INTERNAL_BASE?.replace(/\/$/, "") || undefined,
    clientId: required("OIDC_CLIENT_ID"),
    clientSecret: process.env.OIDC_CLIENT_SECRET || undefined,
    redirectUri: new URL("/auth/callback", appBaseUrl()).toString(),
  };
}

/**
 * The IT service desk's extension for S-02's help lines ("[EXTENSION]" on the boards). IT gives the number
 * (P-DECISIONS.signoff/5); until then the lines leave it out rather than show a placeholder.
 */
export function itServiceDeskExtension(): string | null {
  return envText("IT_SERVICE_DESK_EXTENSION");
}

/**
 * A setting's text, or null when it is unset or empty. Docker Compose reads `KEY=   # note` as the value "# note",
 * so a value that starts with "#" is a comment and counts as unset, as the worker's settings treat it
 * (services/worker/core/config.py `_no_comment_values`; BLD-A224).
 */
export function envText(name: string): string | null {
  const value = process.env[name]?.trim();
  return value && !value.startsWith("#") ? value : null;
}
