import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { measureList, oneName } from "@/lib/measures";
import { currentUser } from "@/server/auth/current";
import { leaderboard } from "@/server/ones";

export const metadata: Metadata = { title: "The Ones leaderboard" };
export const dynamic = "force-dynamic";

/** For Ones only (DEC-077): people by tier, then measured impact (DEC-083), and teams by line of business. */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const board = await leaderboard(me).catch(() => null);
  if (!board) {
    return (
      <>
        <h1>The Ones leaderboard</h1>
        <p className="notice">
          The leaderboard is for Ones. Everyone can see the Ones on the <Link href="/wall">wall</Link>.
        </p>
      </>
    );
  }
  return (
    <>
      <h1>The Ones leaderboard</h1>
      <p className="lead">Only Ones see this. Ranked by tier, then by impact measured after shipping.</p>
      <p className="coming-soon coming-soon-light">Impact weights: coming soon</p>
      <section aria-labelledby="lb-people">
        <h2 id="lb-people">People</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Rank</th>
                <th scope="col">No.</th>
                <th scope="col">Name</th>
                <th scope="col">Tier</th>
                <th scope="col">Measured impact</th>
              </tr>
            </thead>
            <tbody>
              {board.people.map((p) => (
                <tr key={p.number} aria-current={p.you ? "true" : undefined}>
                  <td>{p.rank}</td>
                  <td>{p.number}</td>
                  <td>
                    {oneName(p.number, p.name)}
                    {p.you ? " (you)" : ""}
                  </td>
                  <td>
                    <span
                      className="swatch"
                      style={{ background: p.tier_colour, ["--tier" as string]: p.tier_colour }}
                      aria-hidden="true"
                    />
                    {p.tier}, {p.tier_name}
                  </td>
                  <td>
                    {measureList(p.measures)
                      .map(([l, w]) => `${l}: ${w}`)
                      .join(". ") || "Measured after shipping"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section aria-labelledby="lb-teams">
        <h2 id="lb-teams">Teams</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Rank</th>
                <th scope="col">Line of business</th>
                <th scope="col">Ones</th>
                <th scope="col">Highest tier</th>
              </tr>
            </thead>
            <tbody>
              {board.teams.map((t) => (
                <tr key={t.lob}>
                  <td>{t.rank}</td>
                  <td>{t.lob}</td>
                  <td>{t.ones}</td>
                  <td>
                    {t.top_tier}, {t.top_tier_name}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
