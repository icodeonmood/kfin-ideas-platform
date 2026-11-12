import { NextResponse, type NextRequest } from "next/server";

import { BANNERS, type SwitchName } from "@/lib/killswitch-routes";
import { canFlip } from "@/lib/rbac";
import { auditIp, authorize, str } from "@/server/auth/authorize";
import { getDb } from "@/server/db";
import { KillSwitchError, setKillSwitch } from "@/server/killswitch";
import { log } from "@/server/log";

export const dynamic = "force-dynamic";

/** GET /api/admin/kill-switches — every switch, its state, and whether I may flip it (§7.6). */
export async function GET() {
  const me = await authorize("manage_kill_switches");
  if (me instanceof NextResponse) return me;
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
  const me = await authorize("manage_kill_switches");
  if (me instanceof NextResponse) return me;
  const raw = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const body = { name: str(raw.name, 64), state: str(raw.state, 3), reason: str(raw.reason) };
  if (!body.name) return NextResponse.json({ error: "name_required" }, { status: 400 });
  if (!canFlip(me.roles, body.name)) return NextResponse.json({ error: "forbidden" }, { status: 403 });
  try {
    await setKillSwitch({
      name: body.name,
      state: body.state === "on" ? "on" : body.state === "off" ? "off" : (body.state as "on"),
      reason: body.reason ?? "",
      actor: `user:${me.id}`,
      ip: auditIp(request.headers),
    });
  } catch (err) {
    if (err instanceof KillSwitchError) return NextResponse.json({ error: err.message }, { status: 400 });
    // Anything else: the error's class and SQLSTATE only, never its message (BLD-A171), so a failure here can be
    // diagnosed from the logs. CI saw one unexplained 500 on this call.
    log.error("killswitch.set_failed", {
      switch: body.name,
      error_type: err instanceof Error ? err.constructor.name : typeof err,
      sqlstate: typeof (err as { code?: unknown }).code === "string" ? (err as { code: string }).code : null,
    });
    return NextResponse.json({ error: "switch_not_changed" }, { status: 500 });
  }
  return NextResponse.json({ name: body.name, state: body.state });
}
