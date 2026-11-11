import Link from "next/link";

import { OnesCarousel } from "@/components/ones-carousel";
import { currentUser } from "@/server/auth/current";
import { publicOnes } from "@/server/ones";

export const dynamic = "force-dynamic";

/**
 * Home (DEC-099): a greeting, one large glass way in ("Share an idea", the one hot thing on the screen: a lit slash),
 * two quieter routes, and the Ones on a Zed band below.
 */
export default async function Home() {
  const me = await currentUser();
  const firstName = me?.name.split(" ")[0];
  const ones = me?.privacyAccepted ? await publicOnes().catch(() => null) : null;
  return (
    <>
      <div className="home-hero">
        <h1 className="t-display home-title">
          {firstName ? `Hello, ${firstName}` : "Ideas from everyone at KFintech"}
        </h1>
        <p className="lead home-lead">
          Spot a problem, think of a fix, or see a new business we could build? Share it here, find colleagues
          working on the same thing, and follow it all the way until it ships.
        </p>
      </div>
      <ul className="home-routes" aria-label="Where to start">
        <li className="glass home-route home-route-main" data-lit="" data-edge="">
          <span className="home-route-slash" aria-hidden="true">
            <i className="slash" />
          </span>
          <h2>
            <Link href="/share">Share an idea</Link>
          </h2>
          <p>
            A quick capture is one box: say it your way, in any language. The full canvas helps you make it
            stronger.
          </p>
        </li>
        <li className="glass home-route" data-lit="">
          <h2>
            <Link href="/my-ideas">My ideas</Link>
          </h2>
          <p>See where each of your ideas is and what happens next.</p>
        </li>
        <li className="glass home-route" data-lit="">
          <h2>
            <Link href="/wall">Wall</Link>
          </h2>
          <p>Ideas from across KFintech, what is being built and what has shipped.</p>
        </li>
      </ul>
      {ones && !ones.paused ? <OnesCarousel ones={ones.ones} /> : null}
    </>
  );
}
