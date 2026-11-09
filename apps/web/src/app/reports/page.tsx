import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { report } from "@/server/appeals";
import { currentUser } from "@/server/auth/current";

export const metadata: Metadata = { title: "Fairness and calibration" };
export const dynamic = "force-dynamic";

type Cell = string | number | null;
type Row = Record<string, Cell>;

const HEAD: Record<string, string> = {
  group: "Group",
  scored: "Reached scoring",
  shortlist_rate: "Shortlisted",
  pick_rate: "Picked",
  stage: "Stage",
  count: "Count",
  body: "Decided by",
  outcome: "Outcome",
  dimension: "Dimension",
  rounds: "Rounds",
  mean_gap: "Average gap",
  within_one_level: "Within one level",
  ai_differs: "Differs by 2 or more",
  field: "What the desk changed",
  changed: "Times",
  share_of_reviews: "Share of reviews",
};
const WORDS: Record<string, string> = {
  lob: "A LOB committee",
  core: "The core committee",
  open: "Waiting",
  re_score: "Back to scoring",
};

function show(key: string, v: Cell): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number" && /rate|within_one_level|share_of_reviews/.test(key))
    return `${Math.round(v * 100)}%`;
  return WORDS[String(v)] ?? String(v).replace(/_/g, " ");
}

function Table({ caption, rows }: { caption: string; rows: Row[] }) {
  if (!rows.length) return <p>{caption}: nothing in this period.</p>;
  const cols = Object.keys(rows[0]!);
  return (
    <div className="table-wrap" tabIndex={0} role="region" aria-label={`Scrollable table: ${caption}`}>
      <table>
        <caption>{caption}</caption>
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c} scope="col">
                {HEAD[c] ?? c.replace(/_/g, " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td key={c}>{show(c, r[c] ?? null)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type Fairness = {
  period: { from: string; to: string };
  quarter: string;
  quarters: string[];
  breaches: Row[];
  appeals: Row[];
  by_lob: Row[];
  by_location: Row[];
  overrides: Row;
  recusals: Cell;
  identity_reveals: Cell;
  score_consistency: Row;
};
type Calibration = { prescore_vs_committee: Row[]; desk_corrections: Row[]; reviews: Cell };

export default async function Reports({ searchParams }: { searchParams: Promise<{ quarter?: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const { quarter } = await searchParams;
  const [fair, cal] = (await Promise.all([
    report(me, "fairness", quarter),
    report(me, "calibration", quarter),
  ])) as [Fairness, Calibration];
  return (
    <>
      <h1>Fairness and calibration</h1>
      <p>
        Counts only, with names removed. Any count under 5 shows as &quot;fewer than 5&quot;, and a rate based
        on fewer than 5 shows as &quot;too few to show&quot;. Reports cover whole quarters, so that no single
        person can be worked out by comparing periods.
      </p>
      <form method="get" aria-label="Choose the quarter">
        <div className="field">
          <label htmlFor="r-quarter">Quarter</label>
          <select id="r-quarter" name="quarter" defaultValue={fair.quarter}>
            {fair.quarters.map((q) => (
              <option key={q} value={q}>
                {q.replace("-", " ")}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" className="button button-secondary">
          Show
        </button>
      </form>
      <p className="notice">
        Coming soon: rates by grade (the HR export has no grade yet), measured value against the estimates,
        and agreement with the priority class.
      </p>
      <section aria-labelledby="r-fair" className="panel">
        <h2 id="r-fair">Fairness</h2>
        <p>
          Recusals: {show("", fair.recusals)}. Identity reveals: {show("", fair.identity_reveals)}. Moves past
          the capacity line: {show("", fair.overrides.capacity_line ?? 0)}. Shortlists below the threshold:{" "}
          {show("", fair.overrides.shortlisted_below_threshold ?? 0)}. Rounds with score flags:{" "}
          {show("", fair.score_consistency.with_flags ?? 0)} of {show("", fair.score_consistency.rounds ?? 0)}
          .
        </p>
        <Table caption="Shortlist and pick rates by the contributor's line of business" rows={fair.by_lob} />
        <Table caption="Shortlist and pick rates by location" rows={fair.by_location} />
        <Table caption="Time limits missed, by stage" rows={fair.breaches} />
        <Table caption="Appeals by deciding body and outcome" rows={fair.appeals} />
      </section>
      <section aria-labelledby="r-cal" className="panel">
        <h2 id="r-cal">Calibration</h2>
        <Table
          caption="The assistant's pre-score against the committee's medians"
          rows={cal.prescore_vs_committee}
        />
        <Table
          caption={`How often the review desk changed a proposal (of ${show("", cal.reviews)} reviews)`}
          rows={cal.desk_corrections}
        />
      </section>
    </>
  );
}
