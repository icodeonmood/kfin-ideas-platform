import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { roundView } from "@/server/committee";
import { SubmissionError } from "@/server/submissions";

import { RoundActions, type RoundView } from "./round-actions";

export const metadata: Metadata = { title: "Committee review" };
export const dynamic = "force-dynamic";

function aiText(a: { value: number; rationale: string } | undefined): string {
  return a ? `${a.value}: ${a.rationale}` : "—";
}

export default async function Round({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const id = (await params).id;
  let view: RoundView;
  try {
    view = (await roundView(me, id)) as RoundView;
  } catch (err) {
    if (err instanceof SubmissionError && err.status === 404) notFound();
    throw err;
  }
  const c = view.cluster;
  const rv = view.revealed;
  return (
    <>
      <p>
        <Link href="/committee">Back to the committee</Link>
      </p>
      <h1>
        Review {view.id}: {c.name}
      </h1>
      <p className="notice">
        Blind review: contributors appear as &quot;Contributor 1, 2…&quot; and names of people as labels. The
        consistency check against similar decided groups, and the core brief, are coming soon.
      </p>
      <section aria-labelledby="r-group" className="panel">
        <h2 id="r-group">The group</h2>
        <p>{c.summary?.problem ?? "—"}</p>
        {c.summary?.solution?.length ? (
          <>
            <h3>Proposed fix</h3>
            <ul>
              {c.summary.solution.map((s, i) => (
                <li key={i}>
                  {s.text} <span className="muted">({s.credit.join(", ")})</span>
                </li>
              ))}
            </ul>
          </>
        ) : null}
        <h3>The ideas</h3>
        <ul>
          {c.ideas.map((i, n) => (
            <li key={n}>
              <strong>{i.contributor}:</strong> {i.one_line}
            </li>
          ))}
        </ul>
        <h3>Impact estimate</h3>
        <p>
          Annual net benefit:{" "}
          {view.impact.annual_net_benefit === null
            ? "not estimated"
            : `₹${Math.round(view.impact.annual_net_benefit).toLocaleString("en-IN")}`}
          ; payback: {view.impact.payback_months ?? "—"} months; numbers backed by:{" "}
          {String(view.evidence_type ?? "—").replace(/_/g, " ")} (confidence ×{view.confidence_multiplier}).
        </p>
      </section>
      {rv ? (
        <section aria-labelledby="r-revealed" className="panel">
          <h2 id="r-revealed">Revealed</h2>
          <p>
            Final score: <strong>{rv.final_score ?? "—"}</strong> of 100 (shortlist at{" "}
            {rv.thresholds.shortlist}).
          </p>
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Scrollable table">
            <table>
              <caption>Medians, ranges and the assistant&apos;s pre-score</caption>
              <thead>
                <tr>
                  <th scope="col">Dimension</th>
                  <th scope="col">Median</th>
                  <th scope="col">Range</th>
                  <th scope="col">Assistant</th>
                  <th scope="col">Flags</th>
                </tr>
              </thead>
              <tbody>
                {view.dimensions.map((d) => (
                  <tr key={d.name}>
                    <th scope="row">{d.label}</th>
                    <td>{rv.medians?.[d.name] ?? "—"}</td>
                    <td>{rv.ranges?.[d.name] ?? "—"}</td>
                    <td>{aiText(rv.ai[d.name])}</td>
                    <td>
                      {(rv.flags?.[d.name] ?? [])
                        .map((f) => (f === "members_disagree" ? "Members disagree" : "The assistant differs"))
                        .join("; ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
      <RoundActions id={id} view={view} />
    </>
  );
}
