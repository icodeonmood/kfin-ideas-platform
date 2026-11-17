import type { Metadata } from "next";

import { can, canFlip } from "@/lib/rbac";
import { listGrants } from "@/server/admin/roles";
import { currentUser } from "@/server/auth/current";
import { getDb } from "@/server/db";
import { listFlags } from "@/server/flags";
import { workerJson } from "@/server/worker";

import { Flags } from "./flags";
import { KillSwitches, type Switch } from "./kill-switches";
import { Programme, type ProgrammeView } from "./programme";
import { Roles, type Grant } from "./roles";

export const metadata: Metadata = { title: "Admin" };
export const dynamic = "force-dynamic";

/**
 * The minimal admin page (lane A; SHIP_PLAN_1PC §5; J-ONE steps 1, 2, 3 and 6; L-AUDIT; BLD-A210). Each part shows
 * only to people who may use it, and every action is checked again on the server: the programme (build team,
 * shipped, measurements and Finance, the Ones) for admins, "Take off the Wall" for the review desk and admins, the
 * experiments, roles and kill switches for admins (switches also for InfoSec and HR, each their own). The pack does
 * not draw this page (L-DECIDE.after, L-IMPACT/8 OPEN), so it is plain and staff-facing.
 */
export default async function Admin() {
  const me = await currentUser();
  if (!me) return null;
  const showSwitches = can(me.roles, "manage_kill_switches");
  const showRoles = can(me.roles, "grant_roles");
  const showFlags = can(me.roles, "manage_flags");
  const showProgramme = can(me.roles, "run_programme") || can(me.roles, "take_off_wall");
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
  const programme = showProgramme
    ? await workerJson<ProgrammeView>(`/internal/admin/view/${me.id}`).catch(() => null)
    : null;
  const flags = showFlags ? await listFlags() : [];
  return (
    <>
      <h1>Admin</h1>
      {showProgramme && !programme ? (
        <p role="alert">The programme part of this page didn&apos;t load. Refresh to try again.</p>
      ) : null}
      {programme ? <Programme initial={programme} /> : null}
      {showFlags ? <Flags initial={flags} /> : null}
      {showSwitches ? <KillSwitches initial={switches} /> : null}
      {showSwitches ? (
        <section aria-labelledby="speech-title">
          <h2 id="speech-title">Voice notes</h2>
          <p>
            Voice notes are turned into text by Sarvam, through the gateway. They are on at launch, approved by
            the DPO (DEC-108). <code>capture.voice</code> shows or hides voice notes for everyone.{" "}
            <code>speech.hosted</code> (InfoSec only) lets the audio go to Sarvam. While it is off, voice notes
            can&apos;t be turned into text, so turn <code>capture.voice</code> off too.
          </p>
          <p>
            The audio goes to Sarvam as it is. Typed text is masked before it goes out, and each transcript is
            masked as it comes back.
          </p>
        </section>
      ) : null}
      {showRoles ? <Roles initial={grants} /> : null}
    </>
  );
}
