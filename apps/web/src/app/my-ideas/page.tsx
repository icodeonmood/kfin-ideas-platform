import type { Metadata } from "next";
import Link from "next/link";

import { Status } from "@/components/status";
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
    switchStates().catch(() => new Map<string, "on" | "off">()),
  ]);
  // Committee decisions and appeals live on /appeals (BLD-227). The link shows while the committee flow runs, and
  // while appeals can be filed even if the flow is paused, so nobody loses the way to an open appeal window.
  const committeeOn = isOn(states, "committee.flow") || isOn(states, "appeals.filing");
  return (
    <>
      <h1 className="t-display page-display">My ideas</h1>
      <p className="lead page-lead">
        Every idea you share is listed here with where it is now and what happens next.
      </p>
      {one ? <OneDashboard one={one} /> : null}
      <PointsPanel points={points} />
      <p className="chip-links">
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
        <Status
          kind="error"
          title={<>We can&apos;t load your ideas just now. Please try again in a minute.</>}
        />
      ) : (
        <>
          {mine.ideas.length ? (
            <ul className="idea-list" aria-label="Your ideas">
              {mine.ideas.map((i) => (
                <li key={i.id} className="idea" data-lit="">
                  <h2 className="idea-title">
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
                  <dl className="facts">
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
            <p className="glass empty-note">
              You haven&apos;t shared an idea yet. <Link href="/share">Share an idea</Link>
            </p>
          )}
          {mine.joined.length ? (
            <section className="my-section" aria-labelledby="mi-joined">
              <h2 id="mi-joined" className="t-h2">
                Ideas you teamed up on
              </h2>
              <ul className="idea-list">
                {mine.joined.map((j, n) => (
                  <li key={j.idea_id ?? `joined-${n}`} className="idea" data-lit="">
                    <h3 className="idea-title">
                      {j.with_desk ? (
                        "A related idea is with the review desk"
                      ) : j.idea_id ? (
                        <Link href={`/ideas/${j.idea_id}`}>{j.summary ?? "A colleague's idea"}</Link>
                      ) : (
                        (j.summary ?? "A colleague's idea")
                      )}
                    </h3>
                    <dl className="facts">
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
