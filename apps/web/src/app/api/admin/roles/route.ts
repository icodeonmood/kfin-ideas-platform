import { NextResponse, type NextRequest } from "next/server";

import { authorize, str } from "@/server/auth/authorize";
import { grantRole, listGrants, RoleError } from "@/server/admin/roles";

export const dynamic = "force-dynamic";

/** GET /api/admin/roles — every live role grant (admin only). */
export async function GET() {
  const me = await authorize("grant_roles");
  if (me instanceof NextResponse) return me;
  return NextResponse.json({ grants: await listGrants() });
}

/** POST /api/admin/roles {email, role, scope?, reason} — grant a role; audited. */
export async function POST(request: NextRequest) {
  const me = await authorize("grant_roles");
  if (me instanceof NextResponse) return me;
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const email = str(body.email, 320);
  const role = str(body.role, 40);
  const reason = str(body.reason);
  const scope = body.scope === null || body.scope === undefined ? null : str(body.scope, 40);
  if (!email || !role || reason === undefined || scope === undefined) {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }
  try {
    const id = await grantRole({ email, role, scope, reason, actor: `user:${me.id}`, actorUserId: me.id });
    return NextResponse.json({ id }, { status: 201 });
  } catch (err) {
    if (err instanceof RoleError) return NextResponse.json({ error: err.code }, { status: err.status });
    throw err;
  }
}
