import Link from "next/link";
import { Fragment, type CSSProperties, type ReactNode } from "react";

import { SparkMark } from "@/components/spark-mark";
import { promises } from "@/server/promises";
import { publicOnes, type PublicOne } from "@/server/ones";

import { LandingMotion, TiltMark } from "./landing-motion";
import "./landing.css";

/**
 * S-01 Landing: the signed-out front door, with one job, "Share a problem" (S-01.purpose). Copy is verbatim from
 * reference/copy/Landing.md (desktop) and PhoneLanding.md (phone, ≤ 640 px); where the boards' words differ, both
 * are in the page and the width shows one (`ld-desk` / `ld-phone`, display:none hides the other from everyone).
 *
 * - Both buttons go through S-02 "Signing you in" to silent single sign-on with the share intent, then S-04
 *   (S-01.rules/1, L-AUTH.rules/1, 4).
 * - The review time comes from rules/promises.md; if it cannot be read, the page says who reviews, not when
 *   (S-01.rules/2).
 * - The Ones are the three most recent with a public brief; none, or the Ones off the wall, and the slab is
 *   left out (S-01.rules/3).
 * - Sections reveal once on scroll; the accordion is details/summary (S-01.rules/4). Reduced motion: still.
 */

/** Where "Share a problem" goes: S-02's "Signing you in" state, which continues to silent single sign-on. */
export const SHARE_HREF = "/sign-in?signing=1&to=%2Fshare";

const HEADLINE = "Every fix starts with someone who noticed.";

async function reviewDays(): Promise<number | null> {
  try {
    const days = (await promises()).review.decide_by_working_days;
    return Number.isFinite(days) && days > 0 ? days : null;
  } catch {
    return null;
  }
}

async function landingOnes(): Promise<PublicOne[]> {
  try {
    const res = await publicOnes();
    if (res.paused) return [];
    return res.ones.filter((o) => o.brief).slice(0, 3);
  } catch {
    return [];
  }
}

function Ring() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" focusable="false">
      <circle cx="9" cy="9" r="6.5" fill="none" stroke="currentColor" strokeWidth="2.5" />
    </svg>
  );
}

function Slash() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" focusable="false">
      <path d="M4 16 14 2" stroke="#F46835" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

function PlusCross() {
  return (
    <span className="ld-pm" aria-hidden="true">
      <svg
        width="12"
        height="12"
        viewBox="0 0 12 12"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      >
        <path d="M6 1.5v9M1.5 6h9" />
      </svg>
    </span>
  );
}

function Question({ q, open, children }: { q: string; open?: boolean; children: ReactNode }) {
  return (
    <details open={open}>
      <summary>
        {q}
        <PlusCross />
      </summary>
      <p>{children}</p>
    </details>
  );
}

export async function Landing() {
  const [days, ones] = await Promise.all([reviewDays(), landingOnes()]);
  const reviewWho = days ? `The review desk, within ${days} working days` : "The review desk";
  const reviewWhen = days ? `Within ${days} working days, with a reason` : "With a reason";
  return (
    <div className="ld">
      <div className="ld-amb" aria-hidden="true">
        <i className="a1" />
        <i className="a2" />
        <i className="a3" />
        <i className="a4" />
        <i className="a5" />
      </div>
      <LandingMotion />

      <header className="ld-wrap ld-top">
        <Link href="/" className="ld-brand">
          <SparkMark height={26} />
          1% Club
        </Link>
        <nav className="ld-tnav ld-desk" aria-label="On this page">
          <a href="#how">How it works</a>
          <a href="#questions">Questions</a>
        </nav>
      </header>

      <main id="main" tabIndex={-1} className="ld-main">
        <section className="ld-wrap ld-hero" aria-labelledby="hero-h">
          <div>
            <h1 id="hero-h" className="ld-h1">
              {HEADLINE.split(" ").map((word, i) => (
                <Fragment key={i}>
                  {i > 0 ? " " : null}
                  <span className="ld-wb">
                    <span className="ld-w" style={{ "--i": i } as CSSProperties}>
                      {word}
                    </span>
                  </span>
                </Fragment>
              ))}
            </h1>
            <p className="ld-lead ld-desk">
              1% Club is where you share the problems you see at work, in your own words. If one is picked, a
              team fixes it, and you can be part of that team.
            </p>
            <p className="ld-lead ld-phone">
              Share the problems you see at work, in your own words. If one is picked, a team fixes it, and
              you can be part of that team.
            </p>
            <div className="ld-go ld-desk">
              <a href={SHARE_HREF} className="ld-btn">
                Share a problem
              </a>
              <p className="ld-note">
                About two minutes. It signs you in with your KFintech account on the way and lands you
                straight in the box. Been here before? It takes you back in.
              </p>
            </div>
          </div>
          <figure className="ld-fig" data-reveal="">
            <TiltMark />
            <figcaption className="ld-key">
              <span className="ld-k">
                <Ring />A problem someone noticed
              </span>
              <span className="ld-k">
                <Slash />
                Sharing it: the 1%
              </span>
              <span className="ld-k">
                <Ring />
                The fix a team builds
              </span>
            </figcaption>
          </figure>
        </section>

        <section id="how" className="ld-wrap ld-sec ld-desk" aria-labelledby="how-h" data-reveal="">
          <h2 id="how-h" className="ld-h2">
            How it works
          </h2>
          <ol className="ld-trk">
            <li>
              <span className="ld-nd" aria-hidden="true">
                1
              </span>
              <h3 className="ld-tn">You share it</h3>
              <p className="ld-tw">You, in about two minutes</p>
              <p className="ld-td">
                Type it or say it, in any language. You don&apos;t need to know the fix.
              </p>
            </li>
            <li>
              <span className="ld-nd" aria-hidden="true">
                2
              </span>
              <h3 className="ld-tn">It&apos;s reviewed</h3>
              <p className="ld-tw">{reviewWho}</p>
              <p className="ld-td">
                Every problem is read, and you hear back with the reason in plain words.
              </p>
            </li>
            <li>
              <span className="ld-nd" aria-hidden="true">
                3
              </span>
              <h3 className="ld-tn">It&apos;s built</h3>
              <p className="ld-tw">A team, if it&apos;s picked</p>
              <p className="ld-td">
                A team that can fix it takes it on. If you shared a fix, you can join them.
              </p>
            </li>
            <li>
              <span className="ld-nd" aria-hidden="true">
                4
              </span>
              <h3 className="ld-tn">It&apos;s shipped</h3>
              <p className="ld-tw">Everyone</p>
              <p className="ld-td">
                Once it&apos;s live, we measure what changed: time saved, calls avoided, errors caught.
              </p>
            </li>
          </ol>
        </section>

        <section className="ld-wrap ld-sec ld-phone" aria-labelledby="how-h-phone" data-reveal="">
          <h2 id="how-h-phone" className="ld-h2">
            What happens after you share
          </h2>
          <ol className="ld-how">
            <li>
              <h3 className="ld-tn">Shared</h3>
              <p className="ld-tw">You, about two minutes, in any language</p>
            </li>
            <li>
              <h3 className="ld-tn">Checked and matched</h3>
              <p className="ld-tw">Automatic. Personal details hidden</p>
            </li>
            <li>
              <h3 className="ld-tn">Reviewed</h3>
              <p className="ld-tw">{reviewWhen}</p>
            </li>
            <li>
              <h3 className="ld-tn">Built</h3>
              <p className="ld-tw">If picked. You can join the team</p>
            </li>
            <li>
              <h3 className="ld-tn">Shipped</h3>
              <p className="ld-tw">Then we measure what changed</p>
            </li>
          </ol>
        </section>

        <section id="questions" className="ld-wrap ld-sec" aria-labelledby="q-h" data-reveal="">
          <div className="ld-qa">
            <h2 id="q-h" className="ld-h2">
              Questions people ask
            </h2>
            <div className="ld-qs">
              <Question q="Do I need to know how to fix it?" open>
                <span className="ld-desk">
                  No. Most fixes start with someone describing a problem clearly. If you do have a fix in
                  mind, there&apos;s an optional step for it.
                </span>
                <span className="ld-phone">
                  No. Most fixes start with someone describing a problem clearly. If you have a fix in mind,
                  there&apos;s an optional step for it.
                </span>
              </Question>
              <div className="ld-desk">
                <Question q="What can I share?">
                  Anything that slows down your work, your team, our investors or our distributors. A new
                  business we could build counts too.
                </Question>
              </div>
              <Question q="What about customer details?">
                <span className="ld-desk">
                  Leave them out. We also check everything you share, files included, and hide personal
                  details such as folio numbers and phone numbers before anyone reads it.
                </span>
                <span className="ld-phone">
                  Leave them out. We also check everything you share and hide personal details before anyone
                  reads it.
                </span>
              </Question>
              <Question q="What if it isn't picked?">
                You still hear why, from the review desk, with the reason in plain words.
              </Question>
              <Question q="Who are the Ones?">
                <span className="ld-desk">
                  Colleagues whose problems became fixes. Their names go up on the Wall and the office screen.
                  It&apos;s how we say thank you, not the reason to share.
                </span>
                <span className="ld-phone">
                  Colleagues whose problems became fixes. It&apos;s how we say thank you, not the reason to
                  share.
                </span>
              </Question>
            </div>
          </div>
        </section>

        {ones.length ? (
          <section className="ld-wrap" aria-labelledby="ones-h" data-reveal="">
            <div className="ld-slab">
              <h2 id="ones-h" className="ld-h2">
                The Ones so far
              </h2>
              <p className="ld-slab-lead">
                <span className="ld-desk">Colleagues who noticed something, said it, and saw it fixed.</span>
                <span className="ld-phone">Colleagues whose problems became fixes.</span>
              </p>
              <ul className="ld-ones">
                {ones.map((o) => (
                  <li key={o.induction_no} className="ld-one">
                    <span className="ld-dash" aria-hidden="true" style={{ background: o.tier_colour }} />
                    <p className="ld-no">
                      <span className="vh">Number </span>
                      {o.number}
                    </p>
                    {o.name ? <p className="ld-name">{o.name}</p> : null}
                    <p className="ld-idea">{o.line ?? o.brief}</p>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        ) : null}

        <section className="ld-wrap ld-end" aria-labelledby="end-h" data-reveal="">
          <h2 id="end-h" className="ld-big">
            1% spark. 99% sweat. Bring the spark.
          </h2>
          <a href={SHARE_HREF} className="ld-btn ld-desk">
            Share a problem
          </a>
        </section>
      </main>

      <footer className="ld-foot">
        <div className="ld-wrap ld-foot-in">
          <p className="ld-foot-own">1% Club, a KFintech programme</p>
          <p>Part of The Garage</p>
        </div>
      </footer>

      <div className="ld-dock ld-phone">
        <a href={SHARE_HREF} className="ld-btn ld-full">
          Share a problem
        </a>
        <p className="ld-note">
          About two minutes. It signs you in on the way. Been here before? It takes you back in.
        </p>
      </div>
    </div>
  );
}
