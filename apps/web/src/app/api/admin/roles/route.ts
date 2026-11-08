import { NextResponse, type NextRequest } from "next/server";

import { currentUser } from "@/server/auth/current";
import { grantRole, listGrants, RoleError } from "@/server/admin/roles";

export const dynamic = "force-dynamic";

/** GET /api/admin/roles — every live role grant (admin only, by policy). */
export async function GET() {
  return NextResponse.json({ grants: await listGrants() });
}

/** POST /api/admin/roles {email, role, scope?, reason} — grant a role; audited. */
export async function POST(request: NextRequest) {
  const me = await currentUser();
  if (!me) return NextResponse.json({ error: "sign_in_required" }, { status: 401 });
  const body = (await request.json().catch(() => ({}))) as Record<string, string | undefined>;
  try {
    const id = await grantRole({
      email: body.email ?? "",
      role: body.role ?? "",
      scope: body.scope ?? null,
      reason: body.reason ?? "",
      actor: `user:${me.id}`,
      actorUserId: me.id,
    });
    return NextResponse.json({ id }, { status: 201 });
  } catch (err) {
    if (err instanceof RoleError) return NextResponse.json({ error: err.code }, { status: err.status });
    throw err;
  }
}
