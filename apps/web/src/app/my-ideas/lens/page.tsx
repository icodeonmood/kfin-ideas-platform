import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { myLens } from "@/server/points";

export const metadata: Metadata = { title: "Your lens" };
export const dynamic = "force-dynamic";

const n = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** Your own lens (BLD-135): only you see it. Your ideas by where they are, and the groups you are part of, with
 * how many ideas and colleagues are in each. Numbers only: never anyone else's name or words. */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const lens = await myLens(me).catch(() => null);
  return (
    <>
      <p>
        <Link href="/my-ideas">Back to My ideas</Link>
      </p>
      <h1>Your lens</h1>
      <p className="lead">
        Only you see this page. It counts your ideas and the groups you are part of. It never shows who else
        is in a group or what they wrote.
      </p>
      {lens === null ? (
        <p className="notice">We can&apos;t load your lens just now. Please try again in a minute.</p>
      ) : (
        <>
          <section aria-labelledby="ln-ideas">
            <h2 id="ln-ideas">Your ideas, by where they are</h2>
            {lens.shared ? (
              <div className="table-wrap">
                <table className="table">
                  <caption className="visually-hidden">
                    How many of your {n(lens.shared, "shared idea", "shared ideas")} are at each step
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Where it is</th>
                      <th scope="col">Your ideas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(lens.ideas).map(([label, count]) => (
                      <tr key={label}>
                        <th scope="row">{label}</th>
                        <td>{n(count, "idea", "ideas")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted">
                You haven&apos;t shared an idea yet. <Link href="/share">Share an idea</Link>
              </p>
            )}
            {lens.teamed_up ? (
              <p>
                You have teamed up on{" "}
                {n(lens.teamed_up, "colleague's idea or group", "colleagues' ideas or groups")}.
              </p>
            ) : null}
          </section>
          <section aria-labelledby="ln-groups">
            <h2 id="ln-groups">Groups you are part of</h2>
            {lens.groups.length ? (
              <div className="table-wrap">
                <table className="table">
                  <caption className="visually-hidden">Each group you are part of, with counts only</caption>
                  <thead>
                    <tr>
                      <th scope="col">Group</th>
                      <th scope="col">Where it is</th>
                      <th scope="col">Ideas in it</th>
                      <th scope="col">Colleagues with you</th>
                      <th scope="col">How you are in it</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lens.groups.map((g) => (
                      <tr key={g.id}>
                        <th scope="row">
                          {g.id}
                          {g.area ? `, ${g.area}` : ""}
                        </th>
                        <td>{g.stage}</td>
                        <td>{n(g.ideas, "idea", "ideas")} in it</td>
                        <td>{n(g.colleagues, "colleague", "colleagues")} with you</td>
                        <td>{g.how}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted">
                You are not in a group yet. When the review desk groups ideas like yours, or you team up
                through Find your crew, the group shows here.
              </p>
            )}
          </section>
        </>
      )}
    </>
  );
}
