import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { day, historyTime } from "@/lib/dates";
import { currentUser } from "@/server/auth/current";
import { ideaPage, type IdeaPage, type TimelineRow } from "@/server/ideas";
import { SubmissionError } from "@/server/submissions";

import { FollowUpPanel } from "./follow-up-panel";

export const metadata: Metadata = { title: "Idea" };
export const dynamic = "force-dynamic";

const CATEGORY: Record<string, string> = {
  cost_saving: "Cost saving",
  new_revenue: "New revenue",
  both: "Cost saving and new revenue",
  not_sure: "Not sure yet",
};

function text(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join(", ").replace(/_/g, " ");
  return typeof value === "string" ? value : "";
}

function Timeline({ rows, full }: { rows: TimelineRow[]; full: boolean }) {
  return (
    <section className="glass idea-pane" aria-labelledby="ip-timeline">
      <h2 id="ip-timeline" className="t-h2">
        Timeline
      </h2>
      {rows.length ? (
        <ol className="timeline">
          {rows.map((r, n) => (
            <li key={`${r.when}-${n}`}>
              <strong>{r.what}</strong> <span className="muted">· {historyTime(r.when)}</span>
              {full && r.by ? <span className="muted"> · {r.by}</span> : null}
              {full && r.note ? <p className="muted">{r.note}</p> : null}
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">The timeline appears here within a few minutes of each step.</p>
      )}
    </section>
  );
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const id = (await params).id;
  let p: IdeaPage;
  try {
    p = await ideaPage(me, id);
  } catch (err) {
    if (err instanceof SubmissionError && err.status === 404) notFound();
    throw err;
  }

  if (p.view === "public") {
    return (
      <>
        <p className="back-row">
          <Link className="back" href="/wall">
            Back to the wall
          </Link>
        </p>
        <h1 className="page-display idea-headline">{p.card.summary}</h1>
        <dl className="facts idea-facts">
          {p.card.area ? (
            <div>
              <dt>Area</dt>
              <dd>{p.card.area}</dd>
            </div>
          ) : null}
          <div>
            <dt>Where it is</dt>
            <dd>{p.card.stage}</dd>
          </div>
          <div>
            <dt>Colleagues on it</dt>
            <dd>{p.card.colleagues}</dd>
          </div>
        </dl>
        <p className="muted idea-note">
          This is a short summary. The person&apos;s own words stay with them and the review desk.
        </p>
        <Timeline rows={p.timeline} full={false} />
      </>
    );
  }

  const card = p.card as {
    one_line?: string;
    details?: string;
    who?: { segments?: string[] };
    value?: { category?: string };
  };
  return (
    <>
      <p className="back-row">
        {p.owner ? (
          <Link className="back" href="/my-ideas">
            Back to My ideas
          </Link>
        ) : (
          <Link className="back" href="/wall">
            Back to the wall
          </Link>
        )}
      </p>
      <h1 className="page-display idea-headline">{card.one_line || p.idea_id}</h1>
      <p className="lead page-lead">
        {p.idea_id}
        {p.area ? ` · ${p.area}` : ""}
      </p>
      <section aria-labelledby="ip-status" className="glass idea-pane">
        <h2 id="ip-status" className="t-h2">
          Where it is
        </h2>
        <p>
          <strong>{p.status.stage}.</strong>{" "}
          {p.status.next_step ? (
            <>
              Next: {p.status.next_step}
              {p.status.due ? ` ${day(p.status.due)}` : ""}.
            </>
          ) : null}
        </p>
        {p.owner && p.uuid ? <FollowUpPanel uuid={p.uuid} question={p.question ?? null} /> : null}
      </section>
      <section aria-labelledby="ip-canvas" className="glass idea-pane">
        <h2 id="ip-canvas" className="t-h2">
          {p.owner ? "Your canvas" : "The canvas"}
        </h2>
        {card.details ? <p className="original">{card.details}</p> : null}
        <dl className="facts idea-facts">
          {text(card.who?.segments) ? (
            <div>
              <dt>Who it affects</dt>
              <dd>{text(card.who?.segments)}</dd>
            </div>
          ) : null}
          {card.value?.category ? (
            <div>
              <dt>Value</dt>
              <dd>{CATEGORY[card.value.category] ?? text(card.value.category)}</dd>
            </div>
          ) : null}
          {p.strength !== null ? (
            <div>
              <dt>Canvas strength</dt>
              <dd>{p.strength} of 5</dd>
            </div>
          ) : null}
          <div>
            <dt>Who can see it</dt>
            <dd>{p.visibility === "org" ? "Everyone at KFintech, as a short summary" : "Committees only"}</dd>
          </div>
        </dl>
      </section>
      <Timeline rows={p.timeline} full />
    </>
  );
}
