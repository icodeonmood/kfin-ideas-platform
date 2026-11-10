import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { day } from "@/lib/dates";
import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { committeeLearning, type CommitteeProposal } from "@/server/delivery";

import { ProposalActions } from "../learning-actions";

export const metadata: Metadata = { title: "Learning from your decisions" };
export const dynamic = "force-dynamic";

const DIMENSION: Record<string, string> = {
  financial_value: "Financial value",
  customer_experience: "Customer experience",
  risk_compliance: "Risk and compliance",
  reach: "Reach",
  time_to_value: "Time to value",
  effort: "Effort",
};
const EVIDENCE: Record<string, string> = {
  data_backed: "Backed by data",
  estimate: "An estimate",
  anecdote: "An anecdote",
};
const BODY: Record<string, string> = { core: "The core committee" };
const SOON: Record<string, string> = {
  precedents_in_prescore: "Similar past decisions shown in the assistant's pre-score and briefs",
  guidance_notes: "Short guidance notes drafted from your reasons, for you to approve",
  fairness_simulation: "Seeing how a proposed change would move the gaps between groups before you decide",
  band_edges: "Proposals to move the financial value bands, once finance has confirmed enough results",
  apply_rule_version:
    "Writing an approved change into the rules for you (until then the product team does it)",
};

const pct = (v: unknown) => (typeof v === "number" ? `${Math.round(v * 1000) / 10}%` : String(v ?? "–"));
const num = (v: unknown) =>
  typeof v === "number" ? new Intl.NumberFormat("en-IN").format(v) : String(v ?? "–");
const dim = (d: string) => DIMENSION[d] ?? d.replace(/_/g, " ");
const evidence = (field: string) => {
  const kind = field.split(".")[1] ?? field;
  return EVIDENCE[kind] ?? kind.replace(/_/g, " ");
};

function Proposal({ p }: { p: CommitteeProposal }) {
  const x = p.payload;
  const weights = p.kind === "scorecard_weights";
  const line = !weights && x.rule === "routing";
  return (
    <li className="proposal">
      <p className="meta">
        {weights ? "Scorecard weights, for the chair" : "Scoring bands, for the core committee"}, {p.period}
      </p>
      {weights ? (
        <>
          <h3>Your picks weigh the scorecard differently from the rule</h3>
          <p>
            From {num(x.decisions)} decisions in the last 12 months. The dimensions that differ by 10 points
            or more: {(x.differs ?? []).map(dim).join(", ")}.
          </p>
          <div className="table-wrap">
            <table className="table">
              <caption>Weights now and the weights your decisions imply, out of 100</caption>
              <thead>
                <tr>
                  <th scope="col">Dimension</th>
                  <th scope="col">Weight now</th>
                  <th scope="col">Implied by your decisions</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(x.current as Record<string, number>).map(([d, w]) => (
                  <tr key={d}>
                    <th scope="row">{dim(d)}</th>
                    <td>{w}</td>
                    <td>{x.implied?.[d] ?? "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : line ? (
        <>
          <h3>
            Move the shortlist line from {num(x.current)} to {num(x.proposed)}
          </h3>
          <p>
            Over {num(x.rounds)} scoring rounds in the last 12 months, a line at {num(x.proposed)} matches
            what you shortlisted {pct(x.agreement_proposed)} of the time. The line now matches{" "}
            {pct(x.agreement_now)}.
          </p>
        </>
      ) : (
        <>
          <h3>
            {evidence(x.field ?? "")}: change the confidence multiplier from {num(x.current)} to{" "}
            {num(x.proposed)}
          </h3>
          <p>
            {num(x.deliveries)} delivered ideas scored on this kind of evidence reached a median of{" "}
            {num(x.proposed)} of their target at 90 days.
          </p>
        </>
      )}
      {x.fairness.length ? (
        <div className="notice">
          <p>When this was proposed, the fairness check found:</p>
          <ul>
            {x.fairness.map((r) => (
              <li key={r}>{r}.</li>
            ))}
          </ul>
          <p>Approving waits until these gaps close. You can still decline.</p>
        </div>
      ) : null}
      {p.state === "proposed" ? (
        <ProposalActions id={p.id} path="committee/proposals" />
      ) : (
        <p className="muted">
          {p.state === "approved" ? "Approved" : "Declined"}
          {p.decided_at ? ` on ${day(p.decided_at)}` : ""}.
          {p.state === "approved" ? " The product team updates the rule and records the new version." : ""}
        </p>
      )}
    </li>
  );
}

/**
 * Learning from the core committee's decisions (§5.9) and scoring-band proposals (§5.4 step 4), for the core
 * committee. Counts and rates only, never names or idea text. Each change waits for the chair or the committee
 * (non-negotiable 5); nothing changes a rule on its own.
 */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  if (!can(me.roles, "approve_scorecard_changes")) redirect("/");
  const data = await committeeLearning(me).catch(() => null);
  if (!data) return <p className="notice">We can&apos;t load this page just now. Please try again.</p>;
  const open = data.proposals.filter((p) => p.state === "proposed");
  const decided = data.proposals.filter((p) => p.state !== "proposed");
  const agreement = data.reports.agreement?.data as Record<string, unknown> | undefined;
  const rewards = data.reports.committee_rewards?.data as Record<string, unknown> | undefined;
  const bands = data.reports.scoring_band?.data as Record<string, unknown> | undefined;
  const byBody = (agreement?.by_body as { group: string; rounds: unknown; agreement: unknown }[]) ?? [];
  const gaps = (agreement?.dimension_gap as Record<string, unknown>) ?? {};
  const line = bands?.line as Record<string, unknown> | undefined;
  const multipliers = (bands?.multipliers as Record<string, Record<string, unknown>>) ?? {};
  return (
    <>
      <p>
        <Link href="/desk-decisions">Back to Desk decisions</Link>
      </p>
      <h1>Learning from your decisions</h1>
      <p className="lead">
        What your decisions say about the scorecard and the shortlist line. Every change waits for you: the
        chair decides scorecard weights, and the core committee decides scoring bands.
      </p>

      <section aria-labelledby="c-open">
        <h2 id="c-open">Waiting for a decision</h2>
        {open.length ? (
          <ul className="crew-cards" style={{ listStyle: "none", padding: 0 }}>
            {open.map((p) => (
              <Proposal key={p.id} p={p} />
            ))}
          </ul>
        ) : (
          <p className="muted">Nothing is waiting.</p>
        )}
        {decided.length ? (
          <>
            <h3>Recently decided</h3>
            <ul className="crew-cards" style={{ listStyle: "none", padding: 0 }}>
              {decided.map((p) => (
                <Proposal key={p.id} p={p} />
              ))}
            </ul>
          </>
        ) : null}
      </section>

      <section aria-labelledby="c-agree">
        <h2 id="c-agree">How often the assistant&apos;s pre-score agrees with you</h2>
        {agreement ? (
          <>
            <p>
              Over the last 90 days ({num(agreement.rounds)} scoring rounds), the assistant&apos;s pre-score
              would have put a group on the same side of the shortlist line ({num(agreement.line)}) as you did{" "}
              {pct(agreement.agreement)} of the time.
            </p>
            {byBody.length ? (
              <ul>
                {byBody.map((b) => (
                  <li key={b.group}>
                    {BODY[b.group] ?? b.group}: {pct(b.agreement)} over {num(b.rounds)} rounds
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="table-wrap">
              <table className="table">
                <caption>
                  Average gap between the assistant&apos;s rating and your median, on the 1 to 5 scale (above
                  zero: the assistant rated higher)
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Dimension</th>
                    <th scope="col">Average gap</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(gaps).map(([d, g]) => (
                    <tr key={d}>
                      <th scope="row">{dim(d)}</th>
                      <td>{typeof g === "number" ? g.toFixed(2) : String(g)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted">
              A gap that persists leads to a change in the assistant&apos;s wording, which the product lead
              approves after it passes the test sets.
            </p>
          </>
        ) : (
          <p className="muted">This report runs on Monday mornings.</p>
        )}
      </section>

      <section aria-labelledby="c-rewards">
        <h2 id="c-rewards">What your picks reward</h2>
        {rewards ? (
          rewards.implied ? (
            <p>
              From {num(rewards.decisions)} picks and declines in the last 12 months.{" "}
              {(rewards.differs as string[]).length
                ? `Your decisions weigh ${(rewards.differs as string[]).map(dim).join(", ")} differently from the scorecard; the proposal above has the detail.`
                : "Your decisions weigh the dimensions much as the scorecard does."}
            </p>
          ) : (
            <p>
              {num(rewards.decisions)} picks and declines so far in the last 12 months. The comparison needs
              at least {num(rewards.needed)}, with both picks and declines among them.
            </p>
          )
        ) : (
          <p className="muted">This report runs on the 1st of each month.</p>
        )}
      </section>

      <section aria-labelledby="c-bands">
        <h2 id="c-bands">Scoring bands</h2>
        {bands ? (
          <>
            {line?.observed !== undefined ? (
              <p>
                The shortlist line is {num(line.current)}. Over {num(line.rounds)} rounds, the line that best
                matches what you shortlisted is {num(line.observed)} ({pct(line.agreement_at_observed)}{" "}
                against {pct(line.agreement_at_current)} now).
              </p>
            ) : (
              <p>
                {num(line?.rounds)} scored rounds so far in the last 12 months. Checking the shortlist line
                needs at least {num(line?.needed)}.
              </p>
            )}
            <div className="table-wrap">
              <table className="table">
                <caption>Confidence multipliers against what delivered ideas reached at 90 days</caption>
                <thead>
                  <tr>
                    <th scope="col">Evidence</th>
                    <th scope="col">Multiplier now</th>
                    <th scope="col">Median result against target</th>
                    <th scope="col">Delivered ideas</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(multipliers).map(([k, m]) => (
                    <tr key={k}>
                      <th scope="row">{EVIDENCE[k] ?? k}</th>
                      <td>{num(m.current)}</td>
                      <td>{m.observed === null ? `Needs ${num(bands.needed_outcomes)}` : num(m.observed)}</td>
                      <td>{num(m.deliveries)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p className="muted">This report runs on the 1st of each month.</p>
        )}
        {can(me.roles, "view_fairness_reports") ? (
          <p>
            <Link href="/reports">Fairness and calibration, in full</Link>
          </p>
        ) : null}
      </section>

      <section aria-labelledby="c-soon">
        <h2 id="c-soon">Coming soon</h2>
        {data.coming_soon.map((k) => (
          <p key={k} className="coming-soon coming-soon-light">
            {SOON[k] ?? k}: coming soon
          </p>
        ))}
      </section>
    </>
  );
}
