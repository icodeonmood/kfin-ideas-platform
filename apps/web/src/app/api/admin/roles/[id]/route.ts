import { NextResponse, type NextRequest } from "next/server";

import { authorize, str } from "@/server/auth/authorize";
import { revokeRole, RoleError } from "@/server/admin/roles";

/** DELETE /api/admin/roles/{id} {reason} — end a role grant (never deleted; valid_to is set); audited. */
export async function DELETE(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("grant_roles");
  if (me instanceof NextResponse) return me;
  const grantId = (await params).id;
  if (!/^[1-9][0-9]{0,17}$/.test(grantId)) return NextResponse.json({ error: "bad_id" }, { status: 400 });
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const reason = str(body.reason);
  if (reason === undefined) return NextResponse.json({ error: "reason_required" }, { status: 400 });
  try {
    await revokeRole({ grantId, reason, actor: `user:${me.id}` });
  } catch (err) {
    if (err instanceof RoleError) return NextResponse.json({ error: err.code }, { status: err.status });
    throw err;
  }
  return new NextResponse(null, { status: 204 });
}
