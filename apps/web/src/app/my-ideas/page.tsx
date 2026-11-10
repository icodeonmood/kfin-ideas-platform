import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { day } from "@/lib/dates";
import { currentUser } from "@/server/auth/current";
import { myIdeas } from "@/server/ideas";
import { isOn, switchStates } from "@/server/killswitch";
import { myOne, myTeam } from "@/server/ones";
import { myPoints } from "@/server/points";

import { NameOnWall } from "./name-on-wall";
import { OneDashboard } from "./one-dashboard";
import { PointsPanel } from "./points";

export const metadata: Metadata = { title: "My ideas" };

/** Shared, but the person still has a step to take on the scan page (choose, or take something out). */
const WAITING_ON_YOU = new Set(["scanning", "blocked"]);
export const dynamic = "force-dynamic";

export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const [mine, one, team, points, states] = await Promise.all([
    myIdeas(me).catch(() => null),
    myOne(me).catch(() => null),
    myTeam(me).catch(() => null),
    myPoints(me).catch(() => null),
    switchStates(),
  ]);
  // Committee decisions and appeals live on /appeals; the link shows while the committee flow runs (BLD-227).
  const committeeOn = isOn(states, "committee.flow");
  return (
    <>
      <h1>My ideas</h1>
      <p className="lead">Every idea you share is listed here with where it is now and what happens next.</p>
      {one ? <OneDashboard one={one} /> : null}
      <PointsPanel points={points} />
      <p>
        <Link href="/my-ideas/lens">Your lens: your ideas and groups in numbers</Link>
        {" · "}
        <Link href="/journey">How an idea becomes a One</Link>
        {committeeOn ? (
          <>
            {" · "}
            <Link href="/appeals">Committee decisions on your ideas, and appeals</Link>
          </>
        ) : null}
      </p>
      {team && team.people.length ? (
        <p>
          <Link href="/my-team">Your team&apos;s ideas</Link> ({team.people.length} people report to you)
        </p>
      ) : null}
      {mine === null ? (
        <p className="notice">We can&apos;t load your ideas just now. Please try again in a minute.</p>
      ) : (
        <>
          {mine.ideas.length ? (
            <ul className="crew-cards" aria-label="Your ideas">
              {mine.ideas.map((i) => (
                <li key={i.id} className="crew-card">
                  <h2>
                    {i.draft ? (
                      <Link href={`/share/${i.id}`}>Your draft from {day(i.shared_on)}</Link>
                    ) : WAITING_ON_YOU.has(i.stage_key) ? (
                      <Link href={`/share/${i.id}/done`}>{i.one_line ?? `Your idea ${i.idea_id ?? ""}`}</Link>
                    ) : i.idea_id ? (
                      <Link href={`/ideas/${i.idea_id}`}>{i.one_line ?? `Your idea ${i.idea_id}`}</Link>
                    ) : (
                      (i.one_line ?? "Your idea")
                    )}
                  </h2>
                  <dl className="crew-facts">
                    {i.idea_id ? (
                      <div>
                        <dt>Idea</dt>
                        <dd>{i.idea_id}</dd>
                      </div>
                    ) : null}
                    <div>
                      <dt>Where it is</dt>
                      <dd>{i.stage}</dd>
                    </div>
                    <div>
                      <dt>Next step</dt>
                      <dd>
                        {i.next_step}
                        {i.due ? ` ${day(i.due)}` : ""}
                      </dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ul>
          ) : (
            <p className="notice">
              You haven&apos;t shared an idea yet. <Link href="/share">Share an idea</Link>
            </p>
          )}
          {mine.joined.length ? (
            <section aria-labelledby="mi-joined">
              <h2 id="mi-joined">Ideas you teamed up on</h2>
              <ul className="crew-cards">
                {mine.joined.map((j, n) => (
                  <li key={j.idea_id ?? `joined-${n}`} className="crew-card">
                    <h3>
                      {j.with_desk ? (
                        "A related idea is with the review desk"
                      ) : j.idea_id ? (
                        <Link href={`/ideas/${j.idea_id}`}>{j.summary ?? "A colleague's idea"}</Link>
                      ) : (
                        (j.summary ?? "A colleague's idea")
                      )}
                    </h3>
                    <dl className="crew-facts">
                      <div>
                        <dt>How</dt>
                        <dd>{j.how}</dd>
                      </div>
                      <div>
                        <dt>Where it is</dt>
                        <dd>{j.stage}</dd>
                      </div>
                    </dl>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          <NameOnWall initial={mine.name_on_wall} />
        </>
      )}
    </>
  );
}
