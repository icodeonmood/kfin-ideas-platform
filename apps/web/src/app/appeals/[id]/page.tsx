import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { appealView } from "@/server/appeals";
import { currentUser } from "@/server/auth/current";
import { SubmissionError } from "@/server/submissions";

import { AppealDecision } from "./appeal-decision";

export const metadata: Metadata = { title: "Appeal" };
export const dynamic = "force-dynamic";

type View = {
  id: string;
  state: string;
  due_at: string;
  grounds: string[];
  statement: string;
  links: string[];
  hearing_requested: boolean;
  heard_by: string;
  cluster: {
    id: string;
    name: string | null;
    summary: { problem?: string } | null;
    ideas: { contributor: string; one_line: string | null }[];
  };
  decision: {
    id: string;
    body: string;
    outcome: string;
    reason_code: string | null;
    reason: string | null;
    what_would_change: string | null;
    medians: Record<string, number> | null;
    spread: Record<string, number> | null;
    votes: Record<string, number>;
    final_score: number | null;
  };
  panel_size: number;
  i_chair: boolean;
  outcome: string | null;
  reasons: string | null;
};

const GROUNDS: Record<string, string> = {
  process_not_followed: "The process was not followed",
  misunderstood_or_wrongly_merged: "Misunderstood, or grouped wrongly",
  new_evidence: "New evidence",
};
const OUTCOME: Record<string, string> = { parked: "parked", declined: "not taken forward now" };
const words = (s: string) => s.replace(/_/g, " ");

export default async function Appeal({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  let v: View;
  try {
    v = (await appealView(me, (await params).id)) as View;
  } catch (err) {
    if (err instanceof SubmissionError && err.status === 404) notFound();
    throw err;
  }
  const d = v.decision;
  const due = new Date(v.due_at).toLocaleDateString("en-IN", {
    dateStyle: "medium",
    timeZone: "Asia/Kolkata",
  });
  return (
    <>
      <p>
        <Link href="/appeals">Back to appeals</Link>
      </p>
      <h1>
        Appeal {v.id}: {v.cluster.name ?? v.cluster.id}
      </h1>
      <p>
        {v.heard_by === "core_committee"
          ? "A LOB committee's decision: the core committee hears it, minus anyone linked to the group."
          : `A panel of ${v.panel_size} core committee members hears it.`}{" "}
        {v.state === "open" ? `The outcome is due by ${due}.` : ""}
      </p>
      <p className="notice">
        Blind materials: contributors appear as &quot;Contributor 1, 2…&quot; and people&apos;s names as
        labels. Calendar invitations for the hearing are coming soon.
      </p>
      {v.hearing_requested ? (
        <p className="notice">The colleagues asked for a 10-minute hearing. Please arrange it with them.</p>
      ) : null}
      <section aria-labelledby="a-appeal" className="panel">
        <h2 id="a-appeal">The appeal</h2>
        <p>Grounds: {v.grounds.map((g) => GROUNDS[g] ?? words(g)).join("; ")}.</p>
        <p>{v.statement}</p>
        {v.links.length ? (
          <>
            <h3>Links given (the platform never opens them)</h3>
            <ul>
              {v.links.map((l, i) => (
                <li key={i}>{l}</li>
              ))}
            </ul>
          </>
        ) : null}
      </section>
      <section aria-labelledby="a-group" className="panel">
        <h2 id="a-group">The group</h2>
        <p>{v.cluster.summary?.problem ?? "—"}</p>
        <ul>
          {v.cluster.ideas.map((i, n) => (
            <li key={n}>
              <strong>{i.contributor}:</strong> {i.one_line}
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="a-decision" className="panel">
        <h2 id="a-decision">The decision appealed</h2>
        <p>
          {d.id}: {OUTCOME[d.outcome] ?? d.outcome}
          {d.reason_code ? ` (${words(d.reason_code).toLowerCase()})` : ""}. Final score:{" "}
          {d.final_score ?? "—"} of 100.
        </p>
        <p>{d.reason ?? "—"}</p>
        {d.what_would_change ? <p>What would change it: {d.what_would_change}</p> : null}
        {d.medians ? (
          <div
            className="table-wrap"
            tabIndex={0}
            role="region"
            aria-label="Scrollable table: medians and spread"
          >
            <table>
              <caption>Medians and spread (never individual scores)</caption>
              <thead>
                <tr>
                  <th scope="col">Dimension</th>
                  <th scope="col">Median</th>
                  <th scope="col">Spread</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(d.medians).map(([k, m]) => (
                  <tr key={k}>
                    <th scope="row">{words(k)}</th>
                    <td>{m}</td>
                    <td>{d.spread?.[k] ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        <p className="muted">
          Votes:{" "}
          {Object.entries(d.votes)
            .map(([k, n]) => `${words(k)} ${n}`)
            .join(" · ") || "none taken (a preliminary review)"}
        </p>
      </section>
      <AppealDecision
        id={v.id}
        open={v.state === "open"}
        chair={v.i_chair}
        outcome={v.outcome}
        reasons={v.reasons}
      />
    </>
  );
}
