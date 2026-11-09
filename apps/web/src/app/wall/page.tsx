import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { IdeaCard } from "@/components/idea-card";
import { day } from "@/lib/dates";
import { currentUser } from "@/server/auth/current";
import { wall, type PublicCard } from "@/server/ideas";

export const metadata: Metadata = { title: "Wall" };
export const dynamic = "force-dynamic";

function Section({
  id,
  title,
  empty,
  cards,
}: {
  id: string;
  title: string;
  empty: string;
  cards: PublicCard[];
}) {
  return (
    <section aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      {cards.length ? (
        <ul className="crew-cards">
          {cards.map((c) => (
            <IdeaCard key={c.idea_id ?? c.cluster_id} card={c} />
          ))}
        </ul>
      ) : (
        <p className="muted">{empty}</p>
      )}
    </section>
  );
}

export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const w = await wall().catch(() => null);
  return (
    <>
      <h1>Wall</h1>
      <p className="lead">Ideas from across KFintech, what is being built and what has shipped.</p>
      {w === null ? (
        <p className="notice">We can&apos;t load the wall just now. Please try again in a minute.</p>
      ) : w.paused ? (
        <p className="notice">The ideas wall is resting for now. Your own ideas are in My ideas.</p>
      ) : (
        <>
          <Section
            id="w-recent"
            title="Recent ideas"
            empty="The wall fills up as the review desk looks at new ideas."
            cards={w.recent}
          />
          <Section id="w-picked" title="Picked" empty="Nothing picked yet." cards={w.picked} />
          <Section id="w-building" title="Being built" empty="Nothing being built yet." cards={w.in_garage} />
          <Section id="w-shipped" title="Shipped" empty="Nothing shipped yet." cards={w.shipped} />
          <section aria-labelledby="w-showcase">
            <h2 id="w-showcase">Already running</h2>
            {w.showcase.length ? (
              <ul className="crew-cards">
                {w.showcase.map((s) => (
                  <li key={s.solution_id} className="crew-card">
                    <h3>{s.title}</h3>
                    <p>{s.description}</p>
                    <dl className="crew-facts">
                      {s.owner_team ? (
                        <div>
                          <dt>Team that runs it</dt>
                          <dd>{s.owner_team}</dd>
                        </div>
                      ) : null}
                      {s.shipped_on ? (
                        <div>
                          <dt>Live since</dt>
                          <dd>{day(s.shipped_on)}</dd>
                        </div>
                      ) : null}
                    </dl>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">The product team is adding the first solutions.</p>
            )}
          </section>
        </>
      )}
    </>
  );
}
