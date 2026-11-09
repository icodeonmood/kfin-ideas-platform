import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { deskDecisions } from "@/server/review";

import { VetoForm } from "./veto-form";

export const metadata: Metadata = { title: "Desk decisions" };
export const dynamic = "force-dynamic";

function when(at: string | null) {
  return at
    ? new Date(at).toLocaleDateString("en-IN", {
        weekday: "short",
        day: "numeric",
        month: "short",
        timeZone: "Asia/Kolkata",
      })
    : "—";
}

function outcome(d: Record<string, unknown> | null): string {
  if (!d) return "—";
  if (d.action === "redirect") return `Redirected (${String(d.kind).replace(/_/g, " ")})`;
  if (d.action === "hold") return `Held as ${String(d.hold)}`;
  const attach = d.attach as { type?: string; id?: string } | undefined;
  if (attach?.type === "cluster") return `Grouped into ${attach.id}`;
  if (attach?.type === "idea") return `Grouped with ${attach.id}`;
  return "Reviewed, kept on its own";
}

export default async function DeskDecisions() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const data = await deskDecisions().catch(() => null);
  const mayVeto = can(me.roles, "veto_desk_decision");
  return (
    <>
      <h1>Desk decisions</h1>
      <p className="lead">
        Everything the review desk has decided. You can reconsider a decision within 5 working days, with a
        reason.
      </p>
      {can(me.roles, "score") ? (
        <p>
          <Link href="/committee">The committee&apos;s reviews and decisions</Link>
        </p>
      ) : null}
      {data === null ? (
        <p className="notice">We can&apos;t load the decisions just now. Please try again in a minute.</p>
      ) : (
        <>
          {data.disagreements.length ? (
            <section aria-labelledby="disagree-title" className="panel">
              <h2 id="disagree-title">People who disagree</h2>
              <ul>
                {data.disagreements.map((d) => (
                  <li key={d.item_id}>
                    <Link href={`/review/${d.item_id}`}>{d.idea_id}</Link>: {d.summary ?? "—"} (raised{" "}
                    {when(d.at)})
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          <section aria-labelledby="decided-title" className="panel">
            <h2 id="decided-title">Decided</h2>
            {data.decisions.length ? (
              <ul className="crew-cards">
                {data.decisions.map((d) => (
                  <li key={d.item_id} className="crew-card">
                    <h3>
                      <Link href={`/review/${d.item_id}`}>{d.idea_id}</Link>
                    </h3>
                    <p>{d.summary ?? "—"}</p>
                    <dl className="crew-facts">
                      <div>
                        <dt>Final call</dt>
                        <dd>{outcome(d.decision)}</dd>
                      </div>
                      <div>
                        <dt>Decided</dt>
                        <dd>
                          {when(d.decided_at)} by {d.decided_by ?? "the desk"}
                        </dd>
                      </div>
                      {d.note ? (
                        <div>
                          <dt>Reviewer&apos;s note</dt>
                          <dd>{d.note}</dd>
                        </div>
                      ) : null}
                    </dl>
                    {d.vetoed ? (
                      <p className="muted">Reconsidered by the core committee.</p>
                    ) : d.veto_open && mayVeto ? (
                      <VetoForm itemId={d.item_id} until={when(d.veto_until)} />
                    ) : (
                      <p className="muted">The time to reconsider has passed.</p>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p>Nothing decided yet.</p>
            )}
          </section>
        </>
      )}
    </>
  );
}
