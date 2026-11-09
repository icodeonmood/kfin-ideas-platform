import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { onesConsole } from "@/server/ones";

import { OnesConsoleView } from "./console-view";

export const metadata: Metadata = { title: "Ones" };
export const dynamic = "force-dynamic";

/**
 * The committee console's Ones module (DEC-040, DEC-044, DEC-045, DEC-076, DEC-082, DEC-084, DEC-085): every One,
 * every proposal and its state, and the actions each person may take. A white working screen.
 */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  if (!can(me.roles, "view_ones_console")) redirect("/");
  const data = await onesConsole().catch(() => null);
  if (!data)
    return <p className="notice">We can&apos;t load the Ones just now. Please try again in a minute.</p>;
  return (
    <OnesConsoleView
      data={data}
      viewer={{
        id: me.id,
        chair: me.roles.has("core_chair"),
        committee: can(me.roles, "decide_ones"),
        ceo: me.roles.has("ceo"),
        admin: can(me.roles, "carry_out_ones"),
        propose: can(me.roles, "propose_ones"),
      }}
    />
  );
}
