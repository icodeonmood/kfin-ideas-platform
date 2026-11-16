import { NextResponse, type NextRequest } from "next/server";

import { BANNERS } from "@/lib/killswitch-routes";
import { sendCode } from "@/server/auth/codes";
import { emailCodeOn, liveCodeDeps, MailFailed } from "@/server/auth/email-code";
import {
  ATTEMPT_COOKIE,
  attemptCookieOptions,
  attemptKeyHash,
  cleanIntent,
  intentStore,
  newAttemptKey,
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
 * L-AUTH.rules/2-3). Errors: `not_work_email`, `rate_limited`, `account_disabled`, and `too_soon` with
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
    log.error("auth.code_send_failed", { error_type: err instanceof MailFailed ? "mail" : "unexpected" });
    return NextResponse.json({ error: "unavailable" }, { status: 503 });
  }
  if (!result.ok) {
    log.info("auth.code_refused", { error_code: result.error });
    return NextResponse.json(
      {
        error: result.error,
        ...("resendInSeconds" in result ? { resend_in_seconds: result.resendInSeconds } : {}),
      },
      { status: STATUS[result.error] },
    );
  }
  log.info("auth.code_sent");
  const response = NextResponse.json(
    { sent_to: result.sentTo, valid_minutes: result.validMinutes, resend_in_seconds: result.resendInSeconds },
    { headers: { "Cache-Control": "no-store" } },
  );
  // Keep where they were going against the attempt (L-AUTH.rules/4). An explicit `intent.to` is where the person
  // asked to go now, so it replaces a kept attempt's place; without one, the browser's kept attempt stands.
  const raw = (body.intent && typeof body.intent === "object" ? body.intent : {}) as Record<string, unknown>;
  const explicit = typeof raw.to === "string" && raw.to !== "";
  const key = request.cookies.get(ATTEMPT_COOKIE)?.value;
  const now = new Date();
  const kept =
    !explicit && key && key.length <= 128 ? await intentStore().find(attemptKeyHash(key), now) : null;
  if (!kept) {
    const intent = cleanIntent({ to: raw.to, draftId: raw.draft_id, step: raw.step });
    if (worthKeeping(intent) && mayKeepIntent(request, now.getTime())) {
      const fresh = newAttemptKey();
      await intentStore().save(attemptKeyHash(fresh), intent, now);
      response.cookies.set(ATTEMPT_COOKIE, fresh, attemptCookieOptions(secureCookies()));
    } else if (explicit) {
      // Asked for `/` (or over the limit): an older attempt must not send them somewhere else.
      response.cookies.set(ATTEMPT_COOKIE, "", attemptCookieOptions(secureCookies(), 0));
    }
  }
  return response;
}
