import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { clearConflict } from "@/server/committee";
import { asResponse } from "@/server/http";

/** POST /api/admin/conflicts — an admin clears a manager's conflict flag on an open round, with a reason (§3.1).
 * The worker checks the admin role again, refuses contributors' own flags and writes the audit log. */

export async function POST(request: NextRequest) {
  const me = await authorize("grant_roles");
  if (me instanceof NextResponse) return me;
  const body = ((await request.json().catch(() => null)) ?? {}) as Record<string, unknown>;
  try {
    return NextResponse.json(
      await clearConflict(
        me,
        String(body.round_id ?? ""),
        String(body.member_id ?? ""),
        String(body.reason ?? ""),
      ),
    );
  } catch (err) {
    return asResponse(err);
  }
}
