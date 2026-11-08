import { NextResponse, type NextRequest } from "next/server";

import { currentUser } from "@/server/auth/current";
import { privacyNoticeVersion } from "@/server/config";
import { getDb } from "@/server/db";
import { log } from "@/server/log";

/** POST /api/me/privacy-notice {version} — record acceptance of the notice version shown (§6.2, AT-B2-01). */
export async function POST(request: NextRequest) {
  const me = await currentUser();
  if (!me) return NextResponse.json({ error: "sign_in_required" }, { status: 401 });
  const body = (await request.json().catch(() => ({}))) as { version?: unknown };
  if (body.version !== privacyNoticeVersion()) {
    return NextResponse.json(
      { error: "notice_version_changed", current: privacyNoticeVersion() },
      { status: 409 },
    );
  }
  await getDb()
    .insertInto("privacy_acceptances")
    .values({ user_id: me.id, notice_version: privacyNoticeVersion() })
    .onConflict((oc) => oc.doNothing())
    .execute();
  log.info("privacy.accepted", { user_id: me.id, notice_version: privacyNoticeVersion() });
  return NextResponse.json({ accepted: true, version: privacyNoticeVersion() });
}
