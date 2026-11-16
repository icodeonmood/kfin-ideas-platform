/**
 * Single sign-on first (L-AUTH.rules/1, 4, 8; A-API.auth `POST /auth/sso/start`).
 *
 * Start: keep where the person is going on the server against a new attempt (or reuse the attempt they already
 * have, for "Try again"), then send them to the identity provider; `silent` asks it to show nothing.
 * Callback: a silent try the provider cannot complete without the person is not a failure: they see S-02 with the
 * intent still kept. Any other failure gets a reference ("SSO-7F3A, 9:42 am") that is also in the log line.
 */
import { NextResponse, type NextRequest } from "next/server";

import { appBaseUrl } from "../config";
import { log } from "../log";
import { authorizationUrl, OidcError, randomToken } from "./oidc";
import {
  ATTEMPT_COOKIE,
  attemptCookieOptions,
  attemptKeyHash,
  cleanIntent,
  destination,
  intentStore,
  newAttemptKey,
  type Intent,
} from "./intents";
import { newFailureRef } from "./reference";
import {
  cookieOptions,
  readSession,
  sealTx,
  secureCookies,
  SESSION_COOKIE,
  TX_COOKIE,
  TX_TTL_SECONDS,
} from "./session";

export type StartInput = { to?: unknown; draft_id?: unknown; step?: unknown; silent?: unknown };
/** JSON for scripts; a 303 after a form post (S-02's buttons); a 307 for a link (GET). */
type Mode = "json" | "redirect" | "link";

/** Errors a `prompt=none` request returns when the person must see the provider (OIDC Core 3.1.2.6). */
export const SILENT_UNAVAILABLE = new Set([
  "login_required",
  "interaction_required",
  "consent_required",
  "account_selection_required",
]);

/** What the callback should do with an `error` from the provider. */
export function callbackErrorOutcome(error: string, silent: boolean): "show_sign_in" | "failed" {
  return silent && SILENT_UNAVAILABLE.has(error) ? "show_sign_in" : "failed";
}

const truthy = (v: unknown) => v === true || v === "1" || v === "true";

/** `/sign-in?failed=SSO-7F3A&at=…`: the "Could not sign in" state, or `refused` for an account that can't. */
export function failurePath(kind: "failed" | "refused", ref: string, at = new Date()): string {
  return `/sign-in?${kind}=${encodeURIComponent(ref)}&at=${Math.floor(at.getTime() / 1000)}`;
}

/** Logs one failure with its reference and IDs only, and returns the reference. */
export function logFailure(stage: string, errorCode: string, attemptHash?: string): string {
  const ref = newFailureRef();
  log.warn("auth.sign_in_failed", {
    ref,
    stage,
    error_code: errorCode,
    ...(attemptHash ? { attempt_id: attemptHash.slice(0, 32) } : {}),
  });
  return ref;
}

export async function startSso(request: NextRequest, input: StartInput, mode: Mode): Promise<NextResponse> {
  const now = new Date();
  const status = mode === "link" ? 307 : 303;
  const store = intentStore();
  const given = input.to !== undefined || input.draft_id !== undefined;
  let key = request.cookies.get(ATTEMPT_COOKIE)?.value;
  let intent: Intent | null = null;
  if (!given && key && key.length <= 128) intent = await store.find(attemptKeyHash(key), now);
  if (!intent) {
    intent = cleanIntent({ to: input.to, draftId: input.draft_id, step: input.step });
    key = newAttemptKey();
    await store.save(attemptKeyHash(key), intent, now);
  }
  const attemptHash = attemptKeyHash(key!);

  // Already signed in (another tab finished first): straight to where they were going.
  const session = await readSession(request.cookies.get(SESSION_COOKIE)?.value).catch(() => null);
  if (session) {
    await store.use(attemptHash, now);
    const to = destination(intent);
    const response =
      mode === "json"
        ? NextResponse.json({ signed_in: true, to }, { headers: { "Cache-Control": "no-store" } })
        : NextResponse.redirect(new URL(to, appBaseUrl()), status);
    response.cookies.set(ATTEMPT_COOKIE, "", attemptCookieOptions(secureCookies(), 0));
    return response;
  }

  const tx = {
    state: randomToken(),
    nonce: randomToken(),
    verifier: randomToken(48),
    silent: truthy(input.silent),
    iat: Math.floor(now.getTime() / 1000),
  };
  let url: string;
  try {
    url = await authorizationUrl(tx);
  } catch (err) {
    const ref = logFailure("start", err instanceof OidcError ? err.code : "unexpected", attemptHash);
    const response =
      mode === "json"
        ? NextResponse.json({ error: "sso_unavailable", ref }, { status: 503 })
        : NextResponse.redirect(new URL(failurePath("failed", ref, now), appBaseUrl()), status);
    response.cookies.set(ATTEMPT_COOKIE, key!, attemptCookieOptions(secureCookies()));
    return response;
  }
  const response =
    mode === "json"
      ? NextResponse.json({ redirect_url: url }, { headers: { "Cache-Control": "no-store" } })
      : NextResponse.redirect(url, status);
  response.cookies.set(TX_COOKIE, sealTx(tx), { ...cookieOptions(TX_TTL_SECONDS), path: "/auth" });
  response.cookies.set(ATTEMPT_COOKIE, key!, attemptCookieOptions(secureCookies()));
  return response;
}
