import { NextResponse, type NextRequest } from "next/server";

import { currentUser } from "@/server/auth/current";
import { revokeRole, RoleError } from "@/server/admin/roles";

/** DELETE /api/admin/roles/{id} {reason} — end a role grant (never deleted; valid_to is set); audited. */
export async function DELETE(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) return NextResponse.json({ error: "sign_in_required" }, { status: 401 });
  const grantId = (await params).id;
  if (!/^[1-9][0-9]{0,18}$/.test(grantId)) return NextResponse.json({ error: "bad_id" }, { status: 400 });
  const body = (await request.json().catch(() => ({}))) as { reason?: string };
  try {
    await revokeRole({ grantId, reason: body.reason ?? "", actor: `user:${me.id}` });
  } catch (err) {
    if (err instanceof RoleError) return NextResponse.json({ error: err.code }, { status: err.status });
    throw err;
  }
  return new NextResponse(null, { status: 204 });
}
