import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { myTeam } from "@/server/ones";

export const metadata: Metadata = { title: "Your team" };
export const dynamic = "force-dynamic";

/** A manager's private view of their direct reports (DEC-079): counts only, never anyone's idea text. */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const team = await myTeam(me).catch(() => null);
  return (
    <>
      <h1>Your team</h1>
      <p className="lead">
        What the people who report to you have shared and built. Only you see this. Giving them time for their
        ideas is how teams end up named in The Ember.
      </p>
      {!team ? (
        <p className="notice">We can&apos;t load your team just now. Please try again in a minute.</p>
      ) : !team.people.length ? (
        <p className="notice">
          Nobody reports to you in the HR directory. <Link href="/my-ideas">Back to My ideas</Link>
        </p>
      ) : (
        <>
          <p>
            {team.totals.shared} ideas shared, {team.totals.building} picked or being built,{" "}
            {team.totals.shipped} shipped.{" "}
            {team.ones ? `${team.ones} of your team ${team.ones === 1 ? "is a One" : "are Ones"}.` : ""}
          </p>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Shared</th>
                  <th scope="col">Picked or being built</th>
                  <th scope="col">Shipped</th>
                  <th scope="col">One</th>
                </tr>
              </thead>
              <tbody>
                {team.people.map((p) => (
                  <tr key={p.name}>
                    <td>{p.name}</td>
                    <td>{p.shared}</td>
                    <td>{p.building}</td>
                    <td>{p.shipped}</td>
                    <td>
                      {p.one ? (
                        <>
                          <span
                            className="swatch"
                            style={{ background: p.one.tier_colour }}
                            aria-hidden="true"
                          />
                          No. {p.one.number}, {p.one.tier_name}
                        </>
                      ) : (
                        "–"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="coming-soon coming-soon-light">Manager notes and nudges: coming soon</p>
        </>
      )}
    </>
  );
}
