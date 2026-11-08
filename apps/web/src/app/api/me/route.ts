import { NextResponse } from "next/server";

import { currentUser } from "@/server/auth/current";
import { privacyNoticeVersion } from "@/server/config";

export const dynamic = "force-dynamic";

/** GET /api/me — who I am, my roles, my navigation and whether I have accepted the current privacy notice. */
export async function GET() {
  const me = await currentUser();
  if (!me) return NextResponse.json({ error: "sign_in_required" }, { status: 401 });
  return NextResponse.json(
    {
      name: me.name,
      email: me.email,
      contributor_code: me.contributorCode,
      lob_id: me.lobId,
      role_family: me.roleFamily,
      roles: [...me.roles].sort(),
      grants: me.grants,
      nav: me.nav,
      privacy_notice: { version: privacyNoticeVersion(), accepted: me.privacyAccepted },
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
