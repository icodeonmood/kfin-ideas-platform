import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { itemView, mayAct } from "@/server/review";
import { SubmissionError } from "@/server/submissions";

import { Actions, type ItemView } from "./actions";

export const metadata: Metadata = { title: "Review item" };
export const dynamic = "force-dynamic";

const WHO: Record<string, string> = {
  submitter: "from the person",
  suggested: "suggested by the assistant",
  accepted: "suggested, accepted by the person",
  reviewer: "changed by the review desk",
};

function text(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v)) return v.map(text).join(", ");
  if (typeof v === "object")
    return Object.values(v as object)
      .filter((x) => x !== null)
      .map(text)
      .join(", ");
  return String(v).replace(/_/g, " ");
}

const FIELDS: [string, string][] = [
  ["kind", "Kind"],
  ["one_line", "One line"],
  ["details", "Details"],
  ["who.segments", "Who it touches"],
  ["who.frequency_or_reach", "How often or how many"],
  ["value.category", "Category"],
  ["value.play", "Play"],
  ["value.estimate", "Estimate"],
  ["value.basis", "Basis"],
  ["ecosystem.solved_elsewhere", "Solved elsewhere"],
  ["ecosystem.our_advantage", "Why KFintech"],
  ["solution.approach", "The fix"],
];

function at(card: Record<string, unknown>, path: string): unknown {
  return path
    .split(".")
    .reduce<unknown>(
      (n, k) => (n && typeof n === "object" ? (n as Record<string, unknown>)[k] : undefined),
      card,
    );
}

export default async function Item({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const id = (await params).id;
  let view: ItemView;
  try {
    view = (await itemView(me, id)) as ItemView;
  } catch (err) {
    if (err instanceof SubmissionError && err.status === 404) notFound();
    throw err;
  }
  const card = view.idea.card;
  const conf = view.proposals.confidence;
  return (
    <>
      <p>
        <Link href="/review">Back to the queue</Link>
      </p>
      <h1>
        {view.idea.id} <span className="muted">({view.item.type})</span>
      </h1>
      {view.mode === "neutral" ? (
        <p className="notice">
          Names and client details show as labels because this item is not yours to handle.
        </p>
      ) : null}

      <section aria-labelledby="p-submission" className="panel">
        <h2 id="p-submission">Submission</h2>
        <div className="two-col">
          <div>
            <h3>Their words</h3>
            <p className="original">{view.idea.original_text ?? card.details ?? "—"}</p>
          </div>
          <div>
            <h3>Confirmed canvas</h3>
            <dl className="canvas-view">
              {FIELDS.map(([path, label]) => (
                <div key={path}>
                  <dt>{label}</dt>
                  <dd>
                    {text(at(card, path))}
                    {view.idea.provenance[path] ? (
                      <span className="badge">
                        {" "}
                        ({WHO[view.idea.provenance[path]] ?? view.idea.provenance[path]})
                      </span>
                    ) : null}
                  </dd>
                </div>
              ))}
              <div>
                <dt>Strength</dt>
                <dd>{view.idea.strength ?? 0} of 5</dd>
              </div>
            </dl>
            {view.idea.attachments.length ? (
              <>
                <h4>Research files</h4>
                <ul>
                  {view.idea.attachments.map((a) => (
                    <li key={a.id}>
                      {a.state === "clean" ? <a href={`/api/attachments/${a.id}`}>{a.name}</a> : a.name} —{" "}
                      {a.state.replace(/_/g, " ")}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>
        </div>
      </section>

      <section aria-labelledby="p-proposals" className="panel">
        <h2 id="p-proposals">Proposals</h2>
        <dl className="canvas-view">
          {(["areas", "scope", "lobs", "systems", "roles_affected"] as const).map((k) => (
            <div key={k}>
              <dt>{k.replace(/_/g, " ")}</dt>
              <dd>
                {text(view.proposals.system[k])}
                {conf[`system.${k}`] !== undefined ? (
                  <span className="badge"> (confidence {conf[`system.${k}`]})</span>
                ) : null}
              </dd>
            </div>
          ))}
          <div>
            <dt>Suggested action</dt>
            <dd>{text(view.proposals.suggested_action)}</dd>
          </div>
        </dl>
        {view.proposals.flags.length ? (
          <>
            <h3>The assistant&apos;s doubts</h3>
            <ul>
              {view.proposals.flags.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          </>
        ) : null}
        {view.proposals.person_says ? (
          <p>
            <strong>The person says:</strong> {view.proposals.person_says}
          </p>
        ) : null}
      </section>

      <section aria-labelledby="p-evidence" className="panel">
        <h2 id="p-evidence">Evidence</h2>
        {view.candidates.length ? (
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Scrollable table">
            <table>
              <caption>Possible matches, as the judge labelled them</caption>
              <thead>
                <tr>
                  <th scope="col">Item</th>
                  <th scope="col">Label</th>
                  <th scope="col">Reason</th>
                  <th scope="col">Summary</th>
                </tr>
              </thead>
              <tbody>
                {view.candidates.map((c) => (
                  <tr key={c.cid}>
                    <th scope="row">
                      {c.cid}
                      {c.visibility === "committee" ? " (committee only)" : ""}
                    </th>
                    <td>{c.label}</td>
                    <td>{c.reason ?? "—"}</td>
                    <td>{c.summary ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>No matches were found.</p>
        )}
      </section>

      <section aria-labelledby="p-history" className="panel">
        <h2 id="p-history">History</h2>
        <ol>
          {view.history.map((h, i) => (
            <li key={i}>
              {new Date(h.at).toLocaleString("en-IN", {
                dateStyle: "medium",
                timeStyle: "short",
                timeZone: "Asia/Kolkata",
              })}{" "}
              — {h.event.replace(/^idea\./, "").replace(/_/g, " ")} by {h.by}
            </li>
          ))}
        </ol>
      </section>

      {(await mayAct(me, id)) ? <Actions id={id} view={view} me={me.id} /> : null}
    </>
  );
}
