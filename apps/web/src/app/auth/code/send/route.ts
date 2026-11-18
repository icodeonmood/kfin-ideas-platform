import { NextResponse, type NextRequest } from "next/server";

import { BANNERS } from "@/lib/killswitch-routes";
import { sendCode } from "@/server/auth/codes";
import { emailCodeOn, liveCodeDeps, MailFailed } from "@/server/auth/email-code";
import { refusedJson } from "@/server/auth/sso";
import {
  ATTEMPT_COOKIE,
  attemptCookieOptions,
  attemptKeyHash,
  cleanIntent,
  intentStore,
  newAttemptKey,
  PLACE_COOKIE,
  placeCookieOptions,
  sealPlace,
  worthKeeping,
} from "@/server/auth/intents";
import { secureCookies } from "@/server/auth/session";
import { mayKeepIntent } from "@/server/auth/throttle";
import { readJson } from "@/server/http";
import { log } from "@/server/log";

export const dynamic = "force-dynamic";

const STATUS = { not_work_email: 400, account_disabled: 403, rate_limited: 429, too_soon: 429 } as const;

/**
 * POST /auth/code/send `{ email, intent? }` → `{ sent_to, valid_minutes, resend_in_seconds }` (A-API.auth,
 * L-AUTH.rules/2-3). Errors: `not_work_email`, `rate_limited`, `account_disabled` and `unavailable`, each with a
 * reference (`ref`, and `reference` as "SSO-7F3A, 9:42 am", L-AUTH.rules/8); and `too_soon` with
 * `resend_in_seconds` before the countdown ends (V-FIELDS.signin/6).
 */
export async function POST(request: NextRequest) {
  if (!(await emailCodeOn())) {
    return NextResponse.json(
      { error: "paused", switch: "auth.email_code", banner: BANNERS["auth.email_code"] },
      { status: 503, headers: { "Retry-After": "60" } },
    );
  }
  const body = await readJson(request);
  const email = typeof body.email === "string" ? body.email : "";
  let result;
  try {
    result = await sendCode(await liveCodeDeps(), email);
  } catch (err) {
    return refusedJson(request, "code_send", err instanceof MailFailed ? "mail_failed" : "unavailable", 503, {
      error: "unavailable",
    });
  }
  if (!result.ok) {
    // Asking again before the countdown ends is not a failure: the screen shows the countdown.
    if (result.error === "too_soon") {
      return NextResponse.json(
        { error: result.error, resend_in_seconds: result.resendInSeconds },
        { status: STATUS.too_soon },
      );
    }
    return refusedJson(request, "code_send", result.error, STATUS[result.error]);
  }
  log.info("auth.code_sent");
  const response = NextResponse.json(
    { sent_to: result.sentTo, valid_minutes: result.validMinutes, resend_in_seconds: result.resendInSeconds },
    { headers: { "Cache-Control": "no-store" } },
  );
  // Keep where they were going against the attempt (L-AUTH.rules/4). An explicit `intent.to` is where the person
  // asked to go now, so it replaces a kept attempt's place; without one, the browser's kept attempt stands. Over the
  // write limit the place travels in a sealed cookie instead of a row, so it is never dropped (BLD-A177).
  const raw = (body.intent && typeof body.intent === "object" ? body.intent : {}) as Record<string, unknown>;
  const explicit = typeof raw.to === "string" && raw.to !== "";
  const key = request.cookies.get(ATTEMPT_COOKIE)?.value;
  const now = new Date();
  const kept =
    !explicit && key && key.length <= 128 ? await intentStore().find(attemptKeyHash(key), now) : null;
  if (!kept) {
    const intent = cleanIntent({ to: raw.to, draftId: raw.draft_id, step: raw.step });
    const secure = secureCookies();
    const hadPlace = Boolean(request.cookies.get(PLACE_COOKIE));
    if (worthKeeping(intent) && mayKeepIntent(request, now.getTime())) {
      const fresh = newAttemptKey();
      await intentStore().save(attemptKeyHash(fresh), intent, now);
      response.cookies.set(ATTEMPT_COOKIE, fresh, attemptCookieOptions(secure));
      if (hadPlace) response.cookies.set(PLACE_COOKIE, "", placeCookieOptions(secure, 0));
    } else {
      // Asked for `/`, or over the limit: an older attempt must not send them somewhere else.
      if (explicit) response.cookies.set(ATTEMPT_COOKIE, "", attemptCookieOptions(secure, 0));
      if (worthKeeping(intent))
        response.cookies.set(PLACE_COOKIE, sealPlace(intent, now), placeCookieOptions(secure));
      else if (explicit && hadPlace) response.cookies.set(PLACE_COOKIE, "", placeCookieOptions(secure, 0));
    }
  }
  return response;
}
