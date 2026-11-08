/**
 * OpenID Connect, authorisation-code flow with PKCE (§3.1). Works against Microsoft Entra ID (OIDC_MODE=entra)
 * and the local mock IdP (OIDC_MODE=mock).
 *
 * Dev detail: the mock derives its issuer from the Host header. The browser reaches it as localhost:8090 but
 * the web container reaches it as mock-oidc:8080, so server-side calls in dev go to OIDC_INTERNAL_BASE while
 * presenting the public host (node:http; fetch ignores a Host override). Both sides then agree on one issuer,
 * and the ID token is validated against OIDC_ISSUER exactly as in production.
 */
import { createHash, randomBytes } from "node:crypto";
import http from "node:http";
import https from "node:https";

import { createLocalJWKSet, jwtVerify, type JSONWebKeySet, type JWTPayload } from "jose";

import { oidcConfig } from "../config";

type Discovery = { issuer: string; authorization_endpoint: string; token_endpoint: string; jwks_uri: string };

const CACHE_MS = 10 * 60 * 1000;
let discoveryCache: { at: number; value: Discovery } | undefined;
let jwksCache: { at: number; keys: ReturnType<typeof createLocalJWKSet> } | undefined;

export class OidcError extends Error {
  constructor(public code: string) {
    super(code);
  }
}

function request(
  url: string,
  init: { method?: "GET" | "POST"; form?: Record<string, string> } = {},
): Promise<{ status: number; body: string }> {
  const cfg = oidcConfig();
  const target = new URL(url);
  const publicOrigin = new URL(cfg.issuer).origin;
  let hostHeader: string | undefined;
  if (cfg.internalBase && target.origin === publicOrigin) {
    const internal = new URL(cfg.internalBase);
    hostHeader = target.host;
    target.protocol = internal.protocol;
    target.host = internal.host;
  }
  const body = init.form ? new URLSearchParams(init.form).toString() : undefined;
  const lib = target.protocol === "https:" ? https : http;
  return new Promise((resolve, reject) => {
    const req = lib.request(
      target,
      {
        method: init.method ?? "GET",
        timeout: 10_000,
        headers: {
          Accept: "application/json",
          ...(hostHeader ? { Host: hostHeader } : {}),
          ...(body
            ? {
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": Buffer.byteLength(body),
              }
            : {}),
        },
      },
      (res) => {
        let data = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => resolve({ status: res.statusCode ?? 0, body: data }));
      },
    );
    req.on("timeout", () => req.destroy(new OidcError("idp_timeout")));
    req.on("error", () => reject(new OidcError("idp_unreachable")));
    if (body) req.write(body);
    req.end();
  });
}

async function getJson<T>(url: string): Promise<T> {
  const res = await request(url);
  if (res.status !== 200) throw new OidcError("idp_bad_response");
  return JSON.parse(res.body) as T;
}

export async function discovery(): Promise<Discovery> {
  if (discoveryCache && Date.now() - discoveryCache.at < CACHE_MS) return discoveryCache.value;
  const cfg = oidcConfig();
  const value = await getJson<Discovery>(`${cfg.issuer}/.well-known/openid-configuration`);
  if (value.issuer.replace(/\/$/, "") !== cfg.issuer) throw new OidcError("issuer_mismatch");
  discoveryCache = { at: Date.now(), value };
  return value;
}

async function keys(force = false) {
  if (!force && jwksCache && Date.now() - jwksCache.at < CACHE_MS) return jwksCache.keys;
  const jwks = await getJson<JSONWebKeySet>((await discovery()).jwks_uri);
  jwksCache = { at: Date.now(), keys: createLocalJWKSet(jwks) };
  return jwksCache.keys;
}

const b64url = (buf: Buffer) => buf.toString("base64url");
export const randomToken = (bytes = 32) => b64url(randomBytes(bytes));
export const pkceChallenge = (verifier: string) => b64url(createHash("sha256").update(verifier).digest());

export async function authorizationUrl(tx: {
  state: string;
  nonce: string;
  verifier: string;
}): Promise<string> {
  const cfg = oidcConfig();
  const url = new URL((await discovery()).authorization_endpoint);
  url.search = new URLSearchParams({
    response_type: "code",
    client_id: cfg.clientId,
    redirect_uri: cfg.redirectUri,
    scope: "openid profile email",
    state: tx.state,
    nonce: tx.nonce,
    code_challenge: pkceChallenge(tx.verifier),
    code_challenge_method: "S256",
  }).toString();
  return url.toString();
}

export type Claims = {
  subject: string;
  objectId: string | undefined;
  email: string | undefined;
  name: string | undefined;
  employeeId: string | undefined;
};

const text = (v: unknown) => (typeof v === "string" && v.trim() ? v.trim() : undefined);

export async function exchangeCode(code: string, verifier: string, nonce: string): Promise<Claims> {
  const cfg = oidcConfig();
  const form: Record<string, string> = {
    grant_type: "authorization_code",
    code,
    redirect_uri: cfg.redirectUri,
    client_id: cfg.clientId,
    code_verifier: verifier,
  };
  if (cfg.clientSecret) form.client_secret = cfg.clientSecret;
  const res = await request((await discovery()).token_endpoint, { method: "POST", form });
  if (res.status !== 200) throw new OidcError("token_exchange_failed");
  const idToken = (JSON.parse(res.body) as { id_token?: string }).id_token;
  if (!idToken) throw new OidcError("no_id_token");

  let payload: JWTPayload;
  try {
    payload = (await jwtVerify(idToken, await keys(), { issuer: cfg.issuer, audience: cfg.clientId }))
      .payload;
  } catch {
    // Keys may have rotated: refresh once, then give up.
    payload = (await jwtVerify(idToken, await keys(true), { issuer: cfg.issuer, audience: cfg.clientId }))
      .payload;
  }
  if (payload.nonce !== nonce) throw new OidcError("nonce_mismatch");
  if (!payload.sub) throw new OidcError("no_subject");
  return {
    subject: payload.sub,
    objectId: text(payload.oid),
    email: text(payload.email) ?? text(payload.preferred_username) ?? text(payload.upn),
    name: text(payload.name),
    employeeId: text(payload.employeeId) ?? text(payload.employee_id),
  };
}
