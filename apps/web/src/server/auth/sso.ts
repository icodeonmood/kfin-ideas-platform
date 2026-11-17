/**
 * Single sign-on first (L-AUTH.rules/1, 4, 8; A-API.auth `POST /auth/sso/start`).
 *
 * Start: keep where the person is going on the server against a new attempt (or reuse the attempt they already
 * have, for "Try again"), then send them to the identity provider; `silent` asks it to show nothing. A row is
 * written only for somewhere other than `/`, and within a per-address and overall limit; the sealed sign-in cookie
 * carries the place too, so nobody lands in the wrong place over the limit (BLD-A177). With nothing asked and no
 * row, the place the browser's last sealed transaction carried stands.
 * Callback: a silent try the provider cannot complete without the person is not a failure: they see S-02 with the
 * intent still kept. Any other failure gets a reference ("SSO-7F3A, 9:42 am") that is also in the log line. Either
 * way S-02 is given the place as `to`, so "Try again" and the email code still go there without a row.
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
  signInHref,
  worthKeeping,
  type Intent,
} from "./intents";
import { newFailureRef, referenceLabel } from "./reference";
import {
  cookieOptions,
  openTx,
  readSession,
  sameSecret,
  sealTx,
  secureCookies,
  SESSION_COOKIE,
  TX_COOKIE,
  TX_TTL_SECONDS,
} from "./session";
import { mayKeepIntent } from "./throttle";

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

/**
 * `/sign-in?failed=SSO-7F3A&at=…`: the "Could not sign in" state, or `refused` for an account that can't. With a
 * place other than `/`, `&to=` keeps it for "Try again" and the email code (BLD-A177).
 */
export function failurePath(
  kind: "failed" | "refused",
  ref: string,
  at = new Date(),
  place: Intent | null = null,
): string {
  const path = `/sign-in?${kind}=${encodeURIComponent(ref)}&at=${Math.floor(at.getTime() / 1000)}`;
  const to = signInHref(place).split("?")[1];
  return to ? `${path}&${to}` : path;
}

/**
 * A refused email-code request (L-AUTH.rules/8): logged like any sign-in failure, with the reference and IDs only,
 * and answered with the reference and its label ("SSO-7F3A, 9:42 am") for the person to read to the desk.
 */
export function refusedJson(
  request: NextRequest,
  stage: "code_send" | "code_verify",
  error: string,
  status: number,
  extra: Record<string, unknown> = {},
): NextResponse {
  const key = request.cookies.get(ATTEMPT_COOKIE)?.value;
  const ref = logFailure(stage, error, key && key.length <= 128 ? attemptKeyHash(key) : undefined);
  return NextResponse.json(
    { error, ...extra, ref, reference: referenceLabel(ref, Math.floor(Date.now() / 1000)) },
    { status, headers: { "Cache-Control": "no-store" } },
  );
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
  const known = key && key.length <= 128 ? key : undefined;
  let intent: Intent | null = null;
  if (!given && known) intent = await store.find(attemptKeyHash(known), now);
  if (!intent) {
    // Nothing asked and no row (the write limit refused one): the place this attempt's sealed transaction carried.
    const prior = !given && known ? openTx(request.cookies.get(TX_COOKIE)?.value) : null;
    const carried = prior && sameSecret(prior.attempt, attemptKeyHash(known!)) ? prior.next : undefined;
    intent = given
      ? cleanIntent({ to: input.to, draftId: input.draft_id, step: input.step })
      : cleanIntent({ to: carried });
    key = newAttemptKey();
    if (worthKeeping(intent) && mayKeepIntent(request, now.getTime())) {
      await store.save(attemptKeyHash(key), intent, now);
    }
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
    next: destination(intent),
    attempt: attemptHash,
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
        : NextResponse.redirect(new URL(failurePath("failed", ref, now, intent), appBaseUrl()), status);
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
