import type { Metadata } from "next";
import Link from "next/link";

import { can, canFlip } from "@/lib/rbac";
import { listGrants } from "@/server/admin/roles";
import { currentUser } from "@/server/auth/current";
import { getDb } from "@/server/db";

import { KillSwitches, type Switch } from "./kill-switches";
import { Roles, type Grant } from "./roles";

export const metadata: Metadata = { title: "Admin" };
export const dynamic = "force-dynamic";

export default async function Admin() {
  const me = await currentUser();
  if (!me) return null;
  const showSwitches = can(me.roles, "manage_kill_switches");
  const showRoles = can(me.roles, "grant_roles");
  const switches: Switch[] = showSwitches
    ? (
        await getDb()
          .selectFrom("kill_switches")
          .select(["name", "state", "reason", "changed_by", "changed_at"])
          .orderBy("name")
          .execute()
      ).map((r) => ({
        name: r.name,
        state: r.state === "on" ? "on" : "off",
        reason: r.reason,
        changed_by: r.changed_by,
        changed_at: new Date(r.changed_at).toISOString(),
        can_flip: canFlip(me.roles, r.name),
      }))
    : [];
  const grants: Grant[] = showRoles ? (await listGrants()).map((g) => ({ ...g, id: String(g.id) })) : [];
  return (
    <>
      <h1>Admin</h1>
      {can(me.roles, "review_learning") ? (
        <p>
          <Link href="/learning">Learning reports and proposals</Link>
        </p>
      ) : null}
      {showSwitches ? <KillSwitches initial={switches} /> : null}
      {showRoles ? <Roles initial={grants} /> : null}
    </>
  );
}
