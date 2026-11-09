import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { proposalView, type ProposalView } from "@/server/clusters";
import { SubmissionError } from "@/server/submissions";

import { ProposalActions } from "./proposal-actions";

export const metadata: Metadata = { title: "Group proposal" };
export const dynamic = "force-dynamic";

const SKIPPED: Record<string, string> = {
  outlier_check: "The assistant could not check whether every member belongs. Please check each one.",
  summary: "The assistant could not draft the group's name and statement. Please write them below.",
};

function list(v: string[] | undefined) {
  return v && v.length ? v.join(", ") : "—";
}

export default async function ClusterProposal({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const id = (await params).id;
  let view: ProposalView;
  try {
    view = await proposalView(me, id);
  } catch (err) {
    if (err instanceof SubmissionError && err.status === 404) notFound();
    throw err;
  }
  const s = view.summary;
  const credit = (refs: string[]) => refs.map((r) => view.refs[r] ?? r).join(", ");
  return (
    <>
      <p>
        <Link href="/review">Back to the queue</Link>
      </p>
      <h1>
        Group proposal: {view.kind_words} <span className="muted">({view.run_id})</span>
      </h1>
      {view.mode === "neutral" ? (
        <p className="notice">
          Names and client details show as labels because this item is not yours to handle.
        </p>
      ) : null}
      {view.checks_skipped.map((c) => (
        <p key={c} className="notice">
          {SKIPPED[c] ?? c}
        </p>
      ))}
      {view.kind === "split" ? (
        <p className="notice">
          Coming soon: splitting a group from this screen. For now you can read the proposal and turn it down,
          or leave the group as it is.
        </p>
      ) : null}

      <section aria-labelledby="p-what" className="panel">
        <h2 id="p-what">What the batch found</h2>
        <dl className="canvas-view">
          <div>
            <dt>Proposal</dt>
            <dd>{view.kind_words}</dd>
          </div>
          {view.targets.length ? (
            <div>
              <dt>Groups it changes</dt>
              <dd>
                {view.targets
                  .map((t) => `${t.id}${t.title ? ` (${t.title})` : ""}, ${t.member_count} ideas`)
                  .join("; ")}
              </dd>
            </div>
          ) : null}
          <div>
            <dt>Due</dt>
            <dd>
              {view.due_at
                ? new Date(view.due_at).toLocaleDateString("en-IN", {
                    weekday: "short",
                    day: "numeric",
                    month: "short",
                    timeZone: "Asia/Kolkata",
                  })
                : "—"}
            </dd>
          </div>
          {Object.entries(view.metrics).map(([k, v]) => (
            <div key={k}>
              <dt>{k.replace(/_/g, " ")}</dt>
              <dd>{String(v)}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="p-summary" className="panel">
        <h2 id="p-summary">Suggested summary</h2>
        {s ? (
          <>
            <p className="muted">
              Drafted by {view.generated_by ?? "the assistant"}. Check it before you approve.
            </p>
            <dl className="canvas-view">
              <div>
                <dt>Name</dt>
                <dd>{s.name ?? "—"}</dd>
              </div>
              <div>
                <dt>Description (shown to everyone on match cards)</dt>
                <dd>{s.description ?? "—"}</dd>
              </div>
              <div>
                <dt>Combined problem</dt>
                <dd>{s.problem ?? "—"}</dd>
              </div>
              <div>
                <dt>LOBs</dt>
                <dd>{list(s.lobs)}</dd>
              </div>
              <div>
                <dt>Roles affected</dt>
                <dd>{list(s.roles_affected)}</dd>
              </div>
            </dl>
            {s.variations?.length ? (
              <>
                <h3>Variations raised</h3>
                <ul>
                  {s.variations.map((v, i) => (
                    <li key={i}>
                      {view.refs[v.member] ?? v.member}: {v.note}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            <h3>Combined fix (with credit)</h3>
            {s.solution?.length ? (
              <ul>
                {s.solution.map((p, i) => (
                  <li key={i}>
                    {p.text} <span className="muted">(proposed in {credit(p.credit)})</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p>No fix proposed yet.</p>
            )}
            {s.open_questions?.length ? (
              <>
                <h3>Open questions</h3>
                <ul>
                  {s.open_questions.map((q, i) => (
                    <li key={i}>{q}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </>
        ) : (
          <p>No summary yet. Write the name, description and problem when you approve.</p>
        )}
      </section>

      <section aria-labelledby="p-members" className="panel">
        <h2 id="p-members">Members</h2>
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Scrollable table">
          <table>
            <caption>
              {view.members.length} {view.kind === "grow" ? "ideas to add" : "ideas"}
            </caption>
            <thead>
              <tr>
                <th scope="col">Idea</th>
                <th scope="col">One line</th>
                <th scope="col">LOBs</th>
                <th scope="col">Stage</th>
              </tr>
            </thead>
            <tbody>
              {view.members.map((m) => (
                <tr key={m.idea_id}>
                  <th scope="row">
                    <Link href={`/ideas/${m.idea_id}`}>{m.idea_id}</Link>
                  </th>
                  <td>{m.missing ? "No longer available" : (m.one_line ?? "—")}</td>
                  <td>{list(m.lobs)}</td>
                  <td>{m.stage?.replace(/_/g, " ") ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {view.split_groups ? (
          <>
            <h3>Suggested split</h3>
            <ol>
              {view.split_groups.map((g, i) => (
                <li key={i}>{g.join(", ")}</li>
              ))}
            </ol>
          </>
        ) : null}
        {view.dropped.length ? (
          <>
            <h3>Left out</h3>
            <ul>
              {view.dropped.map((d) => (
                <li key={d.idea_id}>
                  {d.idea_id}:{" "}
                  {d.removed_by
                    ? `removed by ${d.removed_by}`
                    : `the check said: ${d.reason || "a different problem"}`}
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </section>

      <ProposalActions id={id} view={view} />
    </>
  );
}
