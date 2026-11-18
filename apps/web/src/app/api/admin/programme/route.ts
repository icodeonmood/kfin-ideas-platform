import { NextResponse } from "next/server";

import { can } from "@/lib/rbac";
import { programmeCall } from "@/server/admin/programme";
import { currentUser } from "@/server/auth/current";

export const dynamic = "force-dynamic";

/** GET /api/admin/programme — what the admin page shows this person: everything for admins, "Take off the Wall"
 * for the review desk (the worker decides from the person's grants). */
export async function GET() {
  const me = await currentUser();
  if (!me) return NextResponse.json({ error: "sign_in_required" }, { status: 401 });
  if (!me.privacyAccepted) return NextResponse.json({ error: "privacy_notice_required" }, { status: 403 });
  if (!can(me.roles, "run_programme") && !can(me.roles, "take_off_wall"))
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  return programmeCall("GET", `/view/${me.id}`, me.id);
}
