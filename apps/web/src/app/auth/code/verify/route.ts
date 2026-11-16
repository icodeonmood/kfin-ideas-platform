import { NextResponse, type NextRequest } from "next/server";

import { BANNERS } from "@/lib/killswitch-routes";
import { verifyCode } from "@/server/auth/codes";
import { emailCodeOn, liveCodeDeps, MailFailed, signedInResponse } from "@/server/auth/email-code";
import { refusedJson } from "@/server/auth/sso";
import { readJson } from "@/server/http";
import { log } from "@/server/log";

export const dynamic = "force-dynamic";

const STATUS = {
  wrong_code: 400,
  code_expired: 400,
  not_work_email: 400,
  account_disabled: 403,
  rate_limited: 429,
} as const;

/**
 * POST /auth/code/verify `{ email, code }` → `{ signed_in: true, to }` (A-API.auth). Errors: `wrong_code` with
 * `{ tries_left }`, `code_expired` with `{ resent, resend_in_seconds }` (a new one was sent, or can be once the
 * countdown ends), `rate_limited`, `account_disabled`, `unavailable`; each with a reference (L-AUTH.rules/8).
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
  const code = typeof body.code === "string" ? body.code : "";
  let result;
  try {
    result = await verifyCode(await liveCodeDeps(), email, code);
  } catch (err) {
    return refusedJson(
      request,
      "code_verify",
      err instanceof MailFailed ? "mail_failed" : "unavailable",
      503,
      { error: "unavailable" },
    );
  }
  if (!result.ok) {
    const extra =
      result.error === "wrong_code"
        ? { tries_left: result.triesLeft }
        : result.error === "code_expired"
          ? { resent: result.resent, resend_in_seconds: result.resendInSeconds }
          : {};
    return refusedJson(request, "code_verify", result.error, STATUS[result.error], extra);
  }
  log.info("auth.signed_in", { user_id: result.userId, route: "email_code" });
  return signedInResponse(request, result.userId);
}
