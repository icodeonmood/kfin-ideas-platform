import { NextResponse, type NextRequest } from "next/server";

import { BANNERS, type SwitchName } from "@/lib/killswitch-routes";
import { canFlip } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { getDb } from "@/server/db";
import { KillSwitchError, setKillSwitch } from "@/server/killswitch";

export const dynamic = "force-dynamic";

/** GET /api/admin/kill-switches — every switch, its state, and whether I may flip it (§7.6). */
export async function GET() {
  const me = await currentUser();
  if (!me) return NextResponse.json({ error: "sign_in_required" }, { status: 401 });
  const rows = await getDb()
    .selectFrom("kill_switches")
    .select(["name", "state", "reason", "changed_by", "changed_at"])
    .orderBy("name")
    .execute();
  return NextResponse.json({
    switches: rows.map((r) => ({
      ...r,
      can_flip: canFlip(me.roles, r.name),
      banner: BANNERS[r.name as SwitchName] ?? null,
    })),
  });
}

/** PUT /api/admin/kill-switches {name, state, reason} — flip one switch; reason required, audited. */
export async function PUT(request: NextRequest) {
  const me = await currentUser();
  if (!me) return NextResponse.json({ error: "sign_in_required" }, { status: 401 });
  const body = (await request.json().catch(() => ({}))) as { name?: string; state?: string; reason?: string };
  if (!body.name) return NextResponse.json({ error: "name_required" }, { status: 400 });
  if (!canFlip(me.roles, body.name)) return NextResponse.json({ error: "forbidden" }, { status: 403 });
  try {
    await setKillSwitch({
      name: body.name,
      state: body.state === "on" ? "on" : body.state === "off" ? "off" : (body.state as "on"),
      reason: body.reason ?? "",
      actor: `user:${me.id}`,
      ip: request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? null,
    });
  } catch (err) {
    if (err instanceof KillSwitchError) return NextResponse.json({ error: err.message }, { status: 400 });
    throw err;
  }
  return NextResponse.json({ name: body.name, state: body.state });
}
