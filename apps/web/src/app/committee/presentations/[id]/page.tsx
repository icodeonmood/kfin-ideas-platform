import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { presentationForCommittee } from "@/server/committee";
import { SubmissionError } from "@/server/submissions";

import { conflictText } from "../../conflict";
import { PresentationActions, type CommitteePresentation } from "./presentation-actions";

export const metadata: Metadata = { title: "Presentation" };
export const dynamic = "force-dynamic";

const STATE: Record<string, string> = {
  invited: "Invited: waiting for the colleagues to pick a slot",
  scheduled: "Scheduled",
  held: "Presented: assessments open",
  decided: "Decided",
};

export default async function Presentation({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const id = (await params).id;
  let view: CommitteePresentation;
  try {
    view = (await presentationForCommittee(me, id)) as CommitteePresentation;
  } catch (err) {
    if (err instanceof SubmissionError && err.status === 404) notFound();
    throw err;
  }
  if (view.conflict) {
    return (
      <>
        <p>
          <Link href="/committee">Back to the committee</Link>
        </p>
        <h1>Presentation {view.id}</h1>
        <p className="notice">{conflictText(view.conflict)}</p>
      </>
    );
  }
  const s = view.sheet;
  return (
    <>
      <p>
        <Link href="/committee">Back to the committee</Link>
      </p>
      <h1>
        Presentation {view.id}: {view.cluster.name}
      </h1>
      <p>
        {STATE[view.state] ?? view.state}
        {view.slot_at
          ? ` · ${new Date(view.slot_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" })}`
          : ""}
      </p>
      <p className="notice">
        Coming soon here: deck upload and pre-read packs, precedents from similar decided groups, the core
        brief&apos;s route, and moving a no-show to the next session automatically.
      </p>
      <section aria-labelledby="p-group" className="panel">
        <h2 id="p-group">The group</h2>
        <p>{view.cluster.summary?.problem ?? "—"}</p>
        {view.qna_notes ? (
          <>
            <h3>Questions and answers</h3>
            <p>{view.qna_notes}</p>
          </>
        ) : null}
      </section>
      {s ? (
        <section aria-labelledby="p-sheet" className="panel">
          <h2 id="p-sheet">Decision sheet</h2>
          <p>
            Votes:{" "}
            {Object.entries(s.tallies)
              .map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`)
              .join(" · ")}
            . Final score: {s.final_score ?? "—"}. Willing to sponsor: {s.sponsors_willing}.
          </p>
          {s.divergence_flags.length ? (
            <p className="notice">
              {s.divergence_flags
                .map((f) =>
                  f === "votes_split"
                    ? "Votes are split: no option has more than half."
                    : "Scores differ by 2 or more on a dimension.",
                )
                .join(" ")}
            </p>
          ) : null}
          {s.themes ? (
            <div className="two-col">
              <div>
                <h3>Strengths</h3>
                <ul>
                  {s.themes.strengths.map((t, i) => (
                    <li key={i}>
                      {t.theme} ({t.count})
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h3>Concerns</h3>
                <ul>
                  {s.themes.concerns.map((t, i) => (
                    <li key={i}>
                      {t.theme} ({t.count})
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            <p>
              The assistant could not group the strengths and concerns; read the assessments&apos; counts
              above.
            </p>
          )}
          {s.conditions?.length ? (
            <>
              <h3>Conditions proposed</h3>
              <ul>
                {s.conditions.map((c, i) => (
                  <li key={i}>{c.text}</li>
                ))}
              </ul>
            </>
          ) : null}
          <p className="muted">
            Route preferences:{" "}
            {Object.entries(s.route_prefs)
              .map(([k, v]) => `${k} ${v}`)
              .join(" · ")}
          </p>
        </section>
      ) : null}
      <PresentationActions id={id} view={view} />
    </>
  );
}
