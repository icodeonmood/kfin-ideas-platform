import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { assignFlag, FlagError } from "@/server/flags";
import { readJson } from "@/server/http";

/** PUT /api/admin/flags/{key}/people {email, variant: "default"|"alternative"|null, reason} — put one person on a
 * version, or back on the share (null) (L-AUDIT.flags "per person"); audited. */
export async function PUT(request: NextRequest, { params }: { params: Promise<{ key: string }> }) {
  const me = await authorize("manage_flags");
  if (me instanceof NextResponse) return me;
  const body = await readJson(request);
  try {
    await assignFlag({
      key: (await params).key,
      email: body.email,
      variant: body.variant ?? null,
      reason: body.reason,
      actorUserId: me.id,
    });
  } catch (err) {
    if (err instanceof FlagError) return NextResponse.json(err.body(), { status: err.status });
    throw err;
  }
  return new NextResponse(null, { status: 204 });
}
