import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { qualifyView } from "@/server/committee";
import { SubmissionError } from "@/server/submissions";

import { QualifyActions, type QualifyView } from "./qualify-actions";

export const metadata: Metadata = { title: "Qualify a group" };
export const dynamic = "force-dynamic";

const PROPOSED: Record<string, string> = {
  pass: "The rules found nothing against it",
  fail: "The rules found a reason to stop here",
  check: "Needs a person to check",
};

function evidence(gate: string, e: Record<string, unknown>): string {
  if (gate === "evidence")
    return `${e.contributors ?? 0} colleagues; ${(e.own_data as string[] | undefined)?.length ?? 0} with their own data; ${e.clean_files ?? 0} research files; ${e.references ?? 0} references`;
  if (gate === "not_solved") {
    const same = (e.same as string[] | undefined) ?? [];
    if (same.length) return `Already running: ${same.join(", ")}`;
    if (e.assistant === "unavailable")
      return "The assistant could not check the solutions found. Please look yourself.";
    return "No running solution matched.";
  }
  if (gate === "not_planned")
    return e.roadmap_connected
      ? "Nothing planned matched."
      : "The delivery roadmap is not connected yet, so nothing can be found.";
  const triggers = (e.triggers as string[] | undefined) ?? [];
  return triggers.length
    ? `Check with compliance: ${triggers.join(", ").replace(/_/g, " ")}`
    : "No compliance trigger found.";
}

export default async function Qualify({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const id = (await params).id;
  let view: QualifyView;
  try {
    view = (await qualifyView(me, id)) as QualifyView;
  } catch (err) {
    if (err instanceof SubmissionError && err.status === 404) notFound();
    throw err;
  }
  const c = view.cluster;
  return (
    <>
      <p>
        <Link href="/review">Back to the queue</Link>
      </p>
      <h1>
        Qualify {c.id}: {c.name}
      </h1>
      <p className="notice">
        Coming soon here: an AI draft of the impact estimate, the core committee brief (build or buy, and
        priority), screens of their own for the compliance and finance reviewers, and evidence replies from
        contributors.
      </p>
      <section aria-labelledby="q-group" className="panel">
        <h2 id="q-group">The group</h2>
        <p>{c.summary?.problem ?? "—"}</p>
        <p className="muted">
          {c.contributors} contributors · LOBs: {c.lobs.join(", ") || "—"} · scope: {c.scope ?? "—"}
        </p>
      </section>
      <section aria-labelledby="q-gates" className="panel">
        <h2 id="q-gates">Gates</h2>
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Scrollable table">
          <table>
            <caption>Each gate: what the rules found, and your call</caption>
            <thead>
              <tr>
                <th scope="col">Gate</th>
                <th scope="col">The rules found</th>
                <th scope="col">Evidence</th>
                <th scope="col">Your call</th>
              </tr>
            </thead>
            <tbody>
              {view.gates.map((g) => (
                <tr key={g.gate}>
                  <th scope="row">{g.label}</th>
                  <td>{PROPOSED[g.proposed ?? ""] ?? "—"}</td>
                  <td>{evidence(g.gate, g.evidence)}</td>
                  <td>
                    {g.result
                      ? `${g.result === "pass" ? "Passed" : "Stopped"}${g.detail ? ` (${g.detail.replace(/_/g, " ")})` : ""} by ${g.confirmed_by}`
                      : "Not confirmed yet"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <QualifyActions id={id} view={view} mayAct={can(me.roles, "work_review_queue")} />
    </>
  );
}
