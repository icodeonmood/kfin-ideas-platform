import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { BANNERS } from "@/lib/killswitch-routes";
import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { runs, type ClusterRun } from "@/server/clusters";
import { switchStates } from "@/server/killswitch";
import { queue, type QueueFilters } from "@/server/review";

import { RunNow } from "./run-now";

export const metadata: Metadata = { title: "Review" };
export const dynamic = "force-dynamic";

const KINDS: [string, string][] = [
  ["", "Any kind"],
  ["problem", "Problem"],
  ["problem_with_solution", "Problem with a fix"],
  ["business_idea", "Business idea"],
];
const CATEGORIES: [string, string][] = [
  ["", "Any category"],
  ["cost_saving", "Cost saving"],
  ["new_revenue", "New revenue"],
  ["both", "Both"],
  ["not_sure", "Not sure"],
];
const BANDS: [string, string][] = [
  ["", "Any confidence"],
  ["low", "Low (under 0.5)"],
  ["medium", "Medium (0.5 to 0.8)"],
  ["high", "High (0.8 and up)"],
];
const TYPES: [string, string][] = [
  ["", "Any item"],
  ["idea", "Idea"],
  ["disagreement", "Disagreement"],
  ["cluster_proposal", "Group proposal"],
  ["working_group_trigger", "Working group"],
  ["qualify", "Qualify a group"],
];

const TYPE_WORDS: Record<string, string> = {
  disagreement: "disagreement",
  cluster_proposal: "group proposal",
  working_group_trigger: "working group",
  qualify: "qualify",
};

function href(type: string, id: number) {
  if (type === "cluster_proposal") return `/review/clusters/${id}`;
  if (type === "working_group_trigger") return `/review/working-groups/${id}`;
  if (type === "qualify") return `/review/qualify/${id}`;
  return `/review/${id}`;
}

function due(at: string | null) {
  if (!at) return "—";
  return new Date(at).toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "Asia/Kolkata",
  });
}

export default async function Review({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const f = (await searchParams) as QueueFilters;
  const rows = await queue(f);
  let lastRun: ClusterRun | null = null;
  let batchOn = false;
  try {
    lastRun = (await runs())[0] ?? null;
    batchOn = (await switchStates()).get("clusters.batch") === "on";
  } catch {
    lastRun = null;
  }
  const select = (name: keyof QueueFilters, label: string, options: [string, string][]) => (
    <div className="field">
      <label htmlFor={`f-${name}`}>{label}</label>
      <select id={`f-${name}`} name={name} defaultValue={f[name] ?? ""}>
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </div>
  );
  return (
    <>
      <h1>Review</h1>
      <p className="lead">
        Ideas waiting for the review desk: soonest due first, then the ones the assistant is least sure about.
      </p>
      <form className="filters" method="get" aria-label="Filter the queue">
        {select("type", "Item", TYPES)}
        {select("kind", "Kind", KINDS)}
        {select("category", "Category", CATEGORIES)}
        {select("band", "Confidence", BANDS)}
        <div className="field">
          <label htmlFor="f-lob">LOB</label>
          <input id="f-lob" name="lob" defaultValue={f.lob ?? ""} placeholder="LOB-mf" />
        </div>
        <div className="field">
          <label htmlFor="f-strength">Strength at least</label>
          <input id="f-strength" name="strength" inputMode="numeric" defaultValue={f.strength ?? ""} />
        </div>
        <div className="field">
          <label htmlFor="f-age">Waiting at least (days)</label>
          <input id="f-age" name="age" inputMode="numeric" defaultValue={f.age ?? ""} />
        </div>
        <button type="submit" className="button">
          Filter
        </button>
      </form>
      <section aria-labelledby="weekly-grouping" className="panel">
        <h2 id="weekly-grouping">Weekly grouping</h2>
        <p>
          Every Sunday night the batch groups reviewed ideas that describe the same problem and puts each
          group here as a proposal. Nothing changes until the desk approves it.
        </p>
        <p>
          {lastRun
            ? `Last run ${lastRun.id}: ${lastRun.state === "done" ? `${lastRun.pool_size ?? 0} ideas looked at, ${lastRun.counts.proposals ?? 0} proposals` : lastRun.state}.`
            : "No run yet."}
        </p>
        {!batchOn ? <p className="notice">{BANNERS["clusters.batch"]}</p> : null}
        {batchOn && can(me.roles, "approve_cluster_proposals") ? <RunNow /> : null}
      </section>
      {rows.length ? (
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Scrollable table">
          <table className="queue">
            <caption>{rows.length} items waiting</caption>
            <thead>
              <tr>
                <th scope="col">Item</th>
                <th scope="col">Summary</th>
                <th scope="col">Kind</th>
                <th scope="col">Strength</th>
                <th scope="col">Confidence</th>
                <th scope="col">Due</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <th scope="row">
                    <Link href={href(r.type, r.id)}>
                      {r.type === "cluster_proposal" ? "Group proposal" : r.idea_id}
                      {r.type !== "idea" && r.type !== "cluster_proposal"
                        ? ` (${TYPE_WORDS[r.type] ?? r.type})`
                        : ""}
                    </Link>
                    {r.check_first ? (
                      <>
                        <br />
                        <strong>Check first</strong>
                      </>
                    ) : null}
                  </th>
                  <td>{r.summary ?? "—"}</td>
                  <td>{r.kind?.replace(/_/g, " ") ?? "—"}</td>
                  <td>{r.strength ?? "—"}</td>
                  <td>{r.band ?? "—"}</td>
                  <td>{due(r.due_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p>Nothing waiting. Well done.</p>
      )}
    </>
  );
}
