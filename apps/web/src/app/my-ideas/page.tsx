import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { day } from "@/lib/dates";
import { currentUser } from "@/server/auth/current";
import { myIdeas } from "@/server/ideas";

import { NameOnWall } from "./name-on-wall";

export const metadata: Metadata = { title: "My ideas" };
export const dynamic = "force-dynamic";

export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const mine = await myIdeas(me).catch(() => null);
  return (
    <>
      <h1>My ideas</h1>
      <p className="lead">Every idea you share is listed here with where it is now and what happens next.</p>
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
