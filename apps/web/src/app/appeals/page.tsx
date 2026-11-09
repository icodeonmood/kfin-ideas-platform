import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { myAppeals } from "@/server/appeals";
import { currentUser } from "@/server/auth/current";

import { AppealForm } from "./appeal-form";

export const metadata: Metadata = { title: "Appeals" };
export const dynamic = "force-dynamic";

type Decision = {
  decision_id: string;
  cluster_id: string;
  name: string | null;
  outcome: string;
  window_closes: string | null;
  can_appeal: boolean;
  appeal_id: string | null;
  appeal_state: string | null;
  appeal_outcome: string | null;
};
type PanelItem = { id: string; cluster_id: string; state: string; due_at: string; outcome: string | null };

const OUTCOME: Record<string, string> = { parked: "Parked for now", declined: "Not taken forward now" };
const APPEAL: Record<string, string> = {
  upheld: "the decision stands",
  re_score: "back to scoring",
  overturned: "overturned",
};
const date = (iso: string) =>
  new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "long", timeZone: "Asia/Kolkata" });

function status(d: Decision): string {
  if (d.appeal_id) {
    return d.appeal_state === "decided"
      ? `Your appeal ${d.appeal_id} was heard: ${APPEAL[d.appeal_outcome ?? ""] ?? "decided"}.`
      : `Your appeal ${d.appeal_id} is with the panel.`;
  }
  if (d.outcome === "parked" && !d.window_closes) {
    return "Parked groups come back for review in a later cycle. A second park can be appealed.";
  }
  return "The time to appeal this decision has passed.";
}

export default async function Appeals() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const data = await myAppeals(me);
  const decisions = data.decisions as Decision[];
  const panel = data.panel as PanelItem[];
  return (
    <>
      <h1>Appeals</h1>
      <p>
        If you think the committee missed something about a group your idea is in, you can appeal once, within
        15 working days of its decision. Committee members who had no part in it hear the appeal.
      </p>
      <p className="notice">
        Coming soon: appealing a review desk decision (for now, use &quot;Disagree with this?&quot; on your
        idea), appealing a missed time limit, and calendar invitations for a 10-minute hearing.
      </p>
      <section aria-labelledby="ap-mine" className="panel">
        <h2 id="ap-mine">Decisions on your groups</h2>
        {decisions.length ? (
          <ul>
            {decisions.map((d) => (
              <li key={d.decision_id}>
                <h3>
                  {d.name ?? d.cluster_id} ({d.cluster_id}): {OUTCOME[d.outcome] ?? d.outcome}
                </h3>
                {d.can_appeal && d.window_closes ? (
                  <AppealForm decisionId={d.decision_id} closes={date(d.window_closes)} />
                ) : (
                  <p>{status(d)}</p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p>No committee decisions on your groups yet.</p>
        )}
      </section>
      {panel.length ? (
        <section aria-labelledby="ap-panel" className="panel">
          <h2 id="ap-panel">Appeals you are hearing</h2>
          <ul>
            {panel.map((a) => (
              <li key={a.id}>
                <Link href={`/appeals/${a.id}`}>
                  {a.id} ({a.cluster_id})
                </Link>{" "}
                ·{" "}
                {a.state === "open"
                  ? `due ${date(a.due_at)}`
                  : `heard: ${APPEAL[a.outcome ?? ""] ?? "decided"}`}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
