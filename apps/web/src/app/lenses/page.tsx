import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { day } from "@/lib/dates";
import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { lenses } from "@/server/delivery";

import { RebuildLenses } from "./rebuild";

export const metadata: Metadata = { title: "Lenses" };

// Each cell says what its number is, so the table still reads when narrow screens stack its rows.
const stagesText = (stages: Record<string, number>, groups: string[]) =>
  groups
    .filter((g) => stages[g])
    .map((g) => `${g}: ${stages[g]}`)
    .join(", ") || "None yet";
const n = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;
export const dynamic = "force-dynamic";

/**
 * Lenses (§4.14): how ideas look from each line of business and each role, rebuilt every Monday. Counts only:
 * never names, never idea text. Committees and admins.
 */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  if (!can(me.roles, "view_lenses")) redirect("/");
  const data = await lenses(me).catch(() => null);
  if (!data)
    return <p className="notice">We can&apos;t load the lenses just now. Please try again in a minute.</p>;
  return (
    <>
      <h1>Lenses</h1>
      <p className="lead">
        Ideas by line of business and by role. Counts only, rebuilt every Monday
        {data.built_at ? `; last built ${day(data.built_at)}` : "; not built yet"}.
      </p>
      {data.can_rebuild ? <RebuildLenses /> : null}

      <section aria-labelledby="l-lob">
        <h2 id="l-lob">By line of business</h2>
        {data.lobs.length ? (
          <div className="table-wrap">
            <table className="table">
              <caption className="visually-hidden">Ideas touching each line of business, by stage</caption>
              <thead>
                <tr>
                  <th scope="col">Line of business</th>
                  <th scope="col">Ideas</th>
                  <th scope="col">Where they are</th>
                  <th scope="col">Needs attention</th>
                  <th scope="col">Delivery</th>
                </tr>
              </thead>
              <tbody>
                {data.lobs.map((l) => (
                  <tr key={l.id}>
                    <th scope="row">{l.name}</th>
                    <td>{n(l.ideas, "idea", "ideas")}</td>
                    <td>{stagesText(l.stages, data.stage_groups)}</td>
                    <td>
                      {n(l.ageing, "waiting", "waiting")} over 5 working days at the desk;{" "}
                      {n(l.cross_lob_groups, "group", "groups")} shared with other lines
                    </td>
                    <td>
                      {l.being_built} being built, {l.measuring} being measured,{" "}
                      {n(l.adoptable, "result", "results")} that met the target
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">Nothing yet. The lenses are built on Monday mornings.</p>
        )}
        {data.lobs.some((l) => l.top_groups.length) ? (
          <>
            <h3>Biggest groups touching each line</h3>
            <ul>
              {data.lobs
                .filter((l) => l.top_groups.length)
                .map((l) => (
                  <li key={l.id}>
                    {l.name}:{" "}
                    {l.top_groups
                      .map((g) => `${g.id} (${g.colleagues} colleagues, ${g.ideas} ideas)`)
                      .join(", ")}
                  </li>
                ))}
            </ul>
          </>
        ) : null}
      </section>

      <section aria-labelledby="l-role">
        <h2 id="l-role">By role</h2>
        {data.roles.length ? (
          <div className="table-wrap">
            <table className="table">
              <caption className="visually-hidden">
                Ideas affecting each role, by stage, with the most common areas
              </caption>
              <thead>
                <tr>
                  <th scope="col">Role</th>
                  <th scope="col">Ideas</th>
                  <th scope="col">Where they are</th>
                  <th scope="col">Most common areas</th>
                </tr>
              </thead>
              <tbody>
                {data.roles.map((r) => (
                  <tr key={r.id}>
                    <th scope="row">{r.name}</th>
                    <td>{n(r.ideas, "idea", "ideas")}</td>
                    <td>{stagesText(r.stages, data.stage_groups)}</td>
                    <td>
                      {r.top_areas.length
                        ? `Most common areas: ${r.top_areas.map((a) => `${a.name} (${a.ideas})`).join(", ")}`
                        : "No areas yet"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">Nothing yet.</p>
        )}
        <p className="coming-soon coming-soon-light">Recurring friction themes for each role: coming soon</p>
      </section>

      <section aria-labelledby="l-people">
        <h2 id="l-people">People around each group</h2>
        <p className="muted">
          For each active group: how many colleagues are in it, and how many more work on closely related
          groups and could be asked to join its working group. Numbers only. Naming them is an identity
          reveal, which only an admin can do, with a reason, and it is logged.
        </p>
        {data.people.length ? (
          <div className="table-wrap">
            <table className="table">
              <caption className="visually-hidden">Colleagues around each active group, counts only</caption>
              <thead>
                <tr>
                  <th scope="col">Group</th>
                  <th scope="col">Colleagues in it</th>
                  <th scope="col">Related groups</th>
                  <th scope="col">Could be asked to join</th>
                </tr>
              </thead>
              <tbody>
                {data.people.map((p) => (
                  <tr key={p.id}>
                    <th scope="row">{p.id}</th>
                    <td>{n(p.colleagues, "colleague", "colleagues")} in it</td>
                    <td>{n(p.related_groups, "related group", "related groups")}</td>
                    <td>{n(p.could_join, "colleague", "colleagues")} who could be asked to join</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No active groups yet.</p>
        )}
        <p>
          Your own view of the groups you are part of is on <Link href="/my-ideas/lens">Your lens</Link>,
          which only you see.
        </p>
      </section>
    </>
  );
}
