/** Server-side settings from the environment. Nothing secret has a default in code. */

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

export const appEnv = () => process.env.APP_ENV ?? "dev";
export const isProductionLike = () => ["uat", "prod"].includes(appEnv());

export function appBaseUrl(): URL {
  return new URL(process.env.APP_BASE_URL ?? "http://localhost:3000");
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
  const mode = (process.env.OIDC_MODE ?? "mock") as OidcMode;
  if (mode !== "mock" && mode !== "entra") throw new Error("OIDC_MODE must be mock or entra");
  if (mode === "mock" && isProductionLike()) throw new Error("OIDC_MODE=mock is not allowed in UAT or prod");
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
