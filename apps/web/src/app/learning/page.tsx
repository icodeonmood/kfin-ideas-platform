import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { day } from "@/lib/dates";
import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { learning } from "@/server/delivery";

import { ProposalActions, PublishProposal, RunLoop } from "./learning-actions";

export const metadata: Metadata = { title: "Learning" };
export const dynamic = "force-dynamic";

const ACTION_WORDS: Record<string, string> = {
  accept_area_tags: "Accepting the suggested area tags",
  accept_scope: "Accepting the suggested scope",
  attach_to_cluster: "Adding an idea to its closest group",
  mark_as_new: "Marking an idea as new",
};
const QUESTION_WORDS: Record<string, string> = {
  one_line: "One line",
  details: "Details",
  who: "Who it affects",
  value: "The value",
  ecosystem: "Who else is involved",
  solution: "The suggested fix",
};

const pct = (v: unknown) => (typeof v === "number" ? `${Math.round(v * 1000) / 10}%` : "–");
const num = (v: unknown) => (typeof v === "number" ? new Intl.NumberFormat("en-IN").format(v) : "–");

/**
 * How the platform learns (§5), for the product team. Reports hold counts and rates only; every proposal waits for
 * a person, and nothing switches to automatic at launch (non-negotiable 5).
 */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  if (!can(me.roles, "review_learning")) redirect("/");
  const data = await learning(me).catch(() => null);
  if (!data)
    return <p className="notice">We can&apos;t load the learning reports just now. Please try again.</p>;
  const open = data.proposals.filter((p) => p.state === "proposed");
  const decided = data.proposals.filter((p) => p.state !== "proposed");
  const drift = data.reports.drift?.data as Record<string, unknown> | undefined;
  const canvas = data.reports.canvas?.data as Record<string, unknown> | undefined;
  const calibration = data.reports.calibration?.data as Record<string, unknown> | undefined;
  const agreement = data.reports.agreement?.data as Record<string, unknown> | undefined;
  return (
    <>
      <p>
        <Link href="/admin">Back to Admin</Link>
      </p>
      <h1>Learning</h1>
      <p className="lead">
        What the platform has noticed, and what waits for you. Nothing here changes a rule, a tag or the
        glossary on its own.
      </p>
      <p>
        Learning jobs:{" "}
        <span className={`state ${data.switched_on ? "state-on" : "state-off"}`}>
          {data.switched_on ? "On" : "Off"}
        </span>{" "}
        <span className="muted">(the learning.jobs switch on the Admin page)</span>
      </p>

      <section aria-labelledby="p-open">
        <h2 id="p-open">Waiting for the product team</h2>
        {open.length ? (
          <ul className="crew-cards" style={{ listStyle: "none", padding: 0 }}>
            {open.map((p) => (
              <li key={p.id} className="proposal">
                <p className="meta">
                  {p.kind === "glossary_term" ? "New term for the glossary" : "A new area tag"}, {p.period}
                </p>
                <h3>
                  {p.kind === "glossary_term" ? p.term : `${p.ideas} ideas that fit their area tags poorly`}
                </h3>
                <p>
                  Seen in {p.ideas} ideas: {p.idea_ids.join(", ")}
                  {p.idea_ids.length < (p.ideas ?? 0) ? " and more" : ""}.
                </p>
                {p.current_tags ? (
                  <p className="muted">
                    Tagged now as{" "}
                    {Object.entries(p.current_tags)
                      .map(([t, n]) => `${t} (${n})`)
                      .join(", ")}
                    {p.lobs && Object.keys(p.lobs).length ? `; lines: ${Object.keys(p.lobs).join(", ")}` : ""}
                    .
                  </p>
                ) : null}
                <ProposalActions id={p.id} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nothing is waiting.</p>
        )}
        <p className="coming-soon coming-soon-light">A definition drafted by the assistant: coming soon</p>
        {decided.length ? (
          <>
            <h3>Recently decided</h3>
            <ul>
              {decided.slice(0, 20).map((p) => (
                <li key={p.id}>
                  {p.kind === "glossary_term" ? p.term : `Area tag group of ${p.ideas} ideas`}: {p.state}
                  {p.decided_at ? ` on ${day(p.decided_at)}` : ""}
                  {p.doc_id
                    ? `. ${p.in_repo ? "In the company repo" : "Being written to the company repo"} as ${p.doc_id}`
                    : ""}
                  {p.can_publish ? <PublishProposal id={p.id} kind={p.kind} term={p.term} /> : null}
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </section>

      <section aria-labelledby="p-themes">
        <h2 id="p-themes">Friction themes by role</h2>
        <p className="muted">
          Each Monday the assistant groups each role&apos;s recent ideas into the problems they keep raising.
          Only the themes you approve show on the lenses page, as counts. No names and no idea text.
        </p>
        {data.role_themes.filter((t) => t.state === "proposed").length ? (
          <ul className="crew-cards" style={{ listStyle: "none", padding: 0 }}>
            {data.role_themes
              .filter((t) => t.state === "proposed")
              .map((t) => (
                <li key={t.id} className="proposal">
                  <p className="meta">
                    {t.role}, {t.period}: from {t.ideas_considered} recent ideas
                  </p>
                  {t.themes.length ? (
                    <ul>
                      {t.themes.map((th) => (
                        <li key={th.name}>
                          <strong>{th.name}</strong> ({th.ideas} ideas). {th.description}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>Nothing recurs for this role yet.</p>
                  )}
                  <ProposalActions id={t.id} path="role-themes" />
                </li>
              ))}
          </ul>
        ) : (
          <p className="muted">Nothing is waiting.</p>
        )}
      </section>

      <section aria-labelledby="p-auto">
        <h2 id="p-auto">How often the review desk accepts the suggestions</h2>
        <p className="muted">
          Of the last 200 high-confidence suggestions of each kind, how many the desk accepted unchanged.
        </p>
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">Acceptance rate by kind of suggestion</caption>
            <thead>
              <tr>
                <th scope="col">Suggestion</th>
                <th scope="col">Accepted unchanged</th>
                <th scope="col">Decisions counted</th>
                <th scope="col">Who decides</th>
              </tr>
            </thead>
            <tbody>
              {data.autonomy.map((a) => (
                <tr key={a.action_type}>
                  <th scope="row">{ACTION_WORDS[a.action_type] ?? a.action_type}</th>
                  <td>{pct(a.rate)} accepted unchanged</td>
                  <td>{a.window} decisions counted</td>
                  <td>{a.mode === "gated" ? "A person decides every time" : "Automatic"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="coming-soon coming-soon-light">Switching a kind to automatic: off at launch</p>
      </section>

      <section aria-labelledby="p-drift">
        <h2 id="p-drift">This week</h2>
        {drift ? (
          <ul>
            <li>
              Suggestions accepted unchanged: {pct(drift.acceptance_this_week)} this week,{" "}
              {pct(drift.acceptance_last_week)} last week.
            </li>
            <li>Model cost: ₹{num(drift.cost_a_day_inr)} a day.</li>
            <li>
              Scans: {num(drift.scans)}; median {num(drift.scan_seconds_median)} seconds, slowest 5% over{" "}
              {num(drift.scan_seconds_p95)} seconds; {pct(drift.fallback_rate)} needed a second try.
            </li>
          </ul>
        ) : (
          <p className="muted">The weekly report runs on Monday mornings.</p>
        )}
      </section>

      <section aria-labelledby="p-canvas">
        <h2 id="p-canvas">The canvas last month</h2>
        {canvas ? (
          <>
            <p>
              {num(canvas.ideas)} ideas: {num(canvas.full)} full canvases and {num(canvas.quick)} quick
              captures, {num(canvas.quick_enriched)} of them filled in later. Median time to complete:{" "}
              {num(canvas.minutes_to_complete_median)} minutes.
            </p>
            <ul>
              {Object.entries((canvas.skip_rate as Record<string, number | null>) ?? {}).map(([k, v]) => (
                <li key={k}>
                  {QUESTION_WORDS[k] ?? k}: left empty {pct(v)}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="muted">The monthly report runs on the 1st.</p>
        )}
      </section>

      <section aria-labelledby="p-cal">
        <h2 id="p-cal">Results against targets last quarter</h2>
        {calibration ? (
          <p>
            {String(calibration.period)}: {num(calibration.closed)} closed, {num(calibration.target_met)} met
            their target. Median result against target: {num(calibration.median_actual_vs_target)}.
          </p>
        ) : (
          <p className="muted">The quarterly report runs on the 1st of each quarter.</p>
        )}
        <p className="muted">
          Proposed changes to scoring bands and scorecard weights from these results and the core
          committee&apos;s decisions go to the core committee, which decides them on its own learning page.
        </p>
      </section>

      <section aria-labelledby="p-agree">
        <h2 id="p-agree">The assistant&apos;s pre-score against the core committee</h2>
        {agreement ? (
          <p>
            Over the last 90 days ({num(agreement.rounds)} scoring rounds), the pre-score put a group on the
            same side of the shortlist line as the committee {pct(agreement.agreement)} of the time. A gap
            that persists is a reason to change the prompt, through the test sets.
          </p>
        ) : (
          <p className="muted">The weekly report runs on Monday mornings.</p>
        )}
      </section>

      <section aria-labelledby="p-run">
        <h2 id="p-run">Run a report now</h2>
        <RunLoop disabled={!data.switched_on} />
      </section>
    </>
  );
}
