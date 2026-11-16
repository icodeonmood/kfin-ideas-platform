import { NextResponse, type NextRequest } from "next/server";

import { BANNERS } from "@/lib/killswitch-routes";
import { verifyCode } from "@/server/auth/codes";
import { emailCodeOn, liveCodeDeps, MailFailed, signedInResponse } from "@/server/auth/email-code";
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
 * `{ tries_left }`, `code_expired` (a new one was sent), `rate_limited`, `account_disabled`.
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
    log.error("auth.code_verify_failed", { error_type: err instanceof MailFailed ? "mail" : "unexpected" });
    return NextResponse.json({ error: "unavailable" }, { status: 503 });
  }
  if (!result.ok) {
    log.info("auth.code_refused", { error_code: result.error });
    const extra =
      result.error === "wrong_code"
        ? { tries_left: result.triesLeft }
        : result.error === "code_expired"
          ? { resent: true }
          : {};
    return NextResponse.json({ error: result.error, ...extra }, { status: STATUS[result.error] });
  }
  log.info("auth.signed_in", { user_id: result.userId, route: "email_code" });
  return signedInResponse(request, result.userId);
}
