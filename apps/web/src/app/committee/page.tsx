import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { rounds } from "@/server/committee";

import { OpenCycle } from "./open-cycle";

export const metadata: Metadata = { title: "Committee" };
export const dynamic = "force-dynamic";

type Round = {
  id: string;
  cluster_id: string;
  body: string;
  lob_id: string | null;
  state: string;
  closes_at: string;
  scored: number;
  voting: number;
  quorum_met: boolean;
  i_scored: boolean;
  outcome: string | null;
  final_score: number | null;
};

const STATE: Record<string, string> = {
  open: "Scoring",
  revealed: "Scores revealed",
  decided: "Decided",
  cancelled: "Cancelled",
};

export default async function Committee() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const data = await rounds(me);
  const list = data.rounds as Round[];
  const presentations = data.presentations as {
    id: string;
    cluster_id: string;
    state: string;
    slot_at: string | null;
  }[];
  return (
    <>
      <h1>Committee</h1>
      <p className="lead">
        Groups of ideas ready for the committee&apos;s written, blind review. Scores stay sealed until
        everyone has scored.
      </p>
      {data.chair ? <OpenCycle /> : null}
      <section aria-labelledby="c-rounds" className="panel">
        <h2 id="c-rounds">Reviews</h2>
        {list.length ? (
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Scrollable table">
            <table>
              <caption>{list.length} reviews</caption>
              <thead>
                <tr>
                  <th scope="col">Review</th>
                  <th scope="col">Committee</th>
                  <th scope="col">Where it is</th>
                  <th scope="col">Scored</th>
                  <th scope="col">Closes</th>
                </tr>
              </thead>
              <tbody>
                {list.map((r) => (
                  <tr key={r.id}>
                    <th scope="row">
                      <Link href={`/committee/rounds/${r.id}`}>
                        {r.id} ({r.cluster_id})
                      </Link>
                    </th>
                    <td>{r.body === "core" ? "Core committee" : `LOB committee (${r.lob_id})`}</td>
                    <td>
                      {STATE[r.state] ?? r.state}
                      {r.outcome ? `: ${r.outcome}` : ""}
                      {r.state === "open" && !r.i_scored ? " (waiting for your scores)" : ""}
                    </td>
                    <td>
                      {r.scored} of {r.voting}
                    </td>
                    <td>
                      {new Date(r.closes_at).toLocaleDateString("en-IN", {
                        day: "numeric",
                        month: "short",
                        timeZone: "Asia/Kolkata",
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>No reviews yet. They open when the chair opens a cycle.</p>
        )}
      </section>
      {presentations.length ? (
        <section aria-labelledby="c-presentations" className="panel">
          <h2 id="c-presentations">Presentations</h2>
          <ul>
            {presentations.map((p) => (
              <li key={p.id}>
                <Link href={`/committee/presentations/${p.id}`}>
                  {p.id} ({p.cluster_id})
                </Link>{" "}
                · {p.state}
                {p.slot_at
                  ? ` · ${new Date(p.slot_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" })}`
                  : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
