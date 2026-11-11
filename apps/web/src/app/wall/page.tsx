import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { IdeaCard } from "@/components/idea-card";
import { Status } from "@/components/status";
import { jerseyProps, OneCardBody } from "@/components/one-card";
import { day } from "@/lib/dates";
import { BANNERS } from "@/lib/killswitch-routes";
import { currentUser } from "@/server/auth/current";
import { wall, type PublicCard } from "@/server/ideas";
import { publicOnes, type PublicOne } from "@/server/ones";

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
    <section className="wall-section" aria-labelledby={id}>
      <h2 id={id} className="t-h2">
        {title}
      </h2>
      {cards.length ? (
        <ul className="idea-list">
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

/** The loudest thing on the wall (DEC-068): every active One, newest first, with what changes if it works. */
function OnesSection({ ones }: { ones: PublicOne[] }) {
  return (
    <section className="ones-band" aria-labelledby="w-ones">
      <h2 id="w-ones" className="t-display ones-band-title">
        The Ones
      </h2>
      <p className="lead-dark">
        Colleagues building what they noticed. If their ideas work, this is what changes.
      </p>
      {ones.length ? (
        <ul className="one-cards">
          {ones.map((o) => (
            <li key={o.number} {...jerseyProps(o)}>
              <OneCardBody one={o} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="lead-dark">The first Ones are named soon.</p>
      )}
    </section>
  );
}

export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const [w, ones] = await Promise.all([wall().catch(() => null), publicOnes().catch(() => null)]);
  return (
    <>
      <div className="band stage wall-top" data-theme="zed" data-glow="1">
        <div className="band-inner wall-top-inner">
          <h1 className="t-display wall-title">Wall</h1>
          <p className="lead wall-lead">
            Ideas from across KFintech, what is being built and what has shipped.
          </p>
          {ones && !ones.paused ? <OnesSection ones={ones.ones} /> : null}
        </div>
      </div>
      {w === null ? (
        <Status
          kind="error"
          role={null}
          title={<>We can&apos;t load the wall just now. Please try again in a minute.</>}
        />
      ) : w.paused ? (
        <p className="paused paused-inline">{BANNERS["wall.public"]}</p>
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
          <section className="wall-section" aria-labelledby="w-showcase">
            <h2 id="w-showcase" className="t-h2">
              Already running
            </h2>
            {w.showcase.length ? (
              <ul className="idea-list">
                {w.showcase.map((s) => (
                  <li key={s.solution_id} className="idea" data-shipped="">
                    <h3 className="idea-title">{s.title}</h3>
                    <p className="idea-desc">{s.description}</p>
                    <dl className="facts">
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
