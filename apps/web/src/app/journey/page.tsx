import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata: Metadata = { title: "How an idea becomes a One" };

const WHITE = "#FFFFFF";
const LEFT = "#9EA3AD";
const RIGHT = "#5C6270";
const SPARK = "#FF5B14";

/** One isometric block (DEC-065): white top, grey sides. `x`, `y` is the top corner; each block is 60 units tall. */
function Block({ x, y }: { x: number; y: number }) {
  return (
    <>
      <polygon points={`${x},${y} ${x + 52},${y + 30} ${x},${y + 60} ${x - 52},${y + 30}`} fill={WHITE} />
      <polygon
        points={`${x - 52},${y + 30} ${x},${y + 60} ${x},${y + 120} ${x - 52},${y + 90}`}
        fill={LEFT}
      />
      <polygon
        points={`${x},${y + 60} ${x + 52},${y + 30} ${x + 52},${y + 90} ${x},${y + 120}`}
        fill={RIGHT}
      />
    </>
  );
}

function Spark({ x, y }: { x: number; y: number }) {
  return (
    <>
      <polygon points={`${x},${y} ${x + 34},${y - 74} ${x + 44},${y - 68}`} fill={SPARK} />
      <circle cx={x + 49} cy={y - 84} r={5} fill={SPARK} />
    </>
  );
}

function Picture({ label, children }: { label: string; children: ReactNode }) {
  return (
    <svg className="journey-art" viewBox="0 0 300 300" role="img" aria-label={label}>
      {children}
    </svg>
  );
}

const STEPS: { title: string; text: string; label: string; art: ReactNode }[] = [
  {
    title: "Share",
    text: "Put a problem, a fix or a business idea on the canvas. The assistant checks it for personal data and helps you finish it.",
    label: "A single block with an orange spark landing on it.",
    art: (
      <>
        <Block x={150} y={110} />
        <Spark x={140} y={148} />
      </>
    ),
  },
  {
    title: "Reviewed, and your crew",
    text: "The review desk reads it within five working days. If colleagues raised the same thing, you team up with them.",
    label: "Two blocks side by side; the spark sits on the first.",
    art: (
      <>
        <Block x={124} y={110} />
        <Block x={176} y={140} />
        <Spark x={116} y={146} />
      </>
    ),
  },
  {
    title: "Picked and being built",
    text: "The core committee shortlists the strongest ideas, hears them and picks some to build. A picked idea gets a team, a sponsor from leadership and protected time, and you become a One with your own number.",
    label: "Three blocks, one stacked on top; the spark rides the top block.",
    art: (
      <>
        <Block x={124} y={130} />
        <Block x={124} y={70} />
        <Block x={176} y={160} />
        <Spark x={116} y={106} />
      </>
    ),
  },
  {
    title: "Shipped and measured",
    text: "It ships. At 30 and 90 days we measure what changed: time given back, money, effort saved and how many people it reaches.",
    label: "A finished tower of blocks with the orange ember on top.",
    art: (
      <>
        <Block x={124} y={150} />
        <Block x={124} y={90} />
        <Block x={124} y={30} />
        <Block x={176} y={180} />
        <circle cx={124} cy={22} r={8} fill={SPARK} />
      </>
    ),
  },
];

/** How an idea travels, told with the isometric blocks (DEC-065, BLD-130): the spark is the only colour. */
export default function Page() {
  return (
    <>
      <div className="brand-band">
        <h1>How an idea becomes a One</h1>
        <p className="lead">You bring the spark. Here is what happens next.</p>
      </div>
      <section className="ones-band" aria-label="The journey, step by step">
        <ol className="journey-steps">
          {STEPS.map((s) => (
            <li key={s.title}>
              <Picture label={s.label}>{s.art}</Picture>
              <h2>{s.title}</h2>
              <p className="lead-dark">{s.text}</p>
            </li>
          ))}
        </ol>
      </section>
      <section aria-labelledby="j-tiers">
        <h2 id="j-tiers">Then your spark gets hotter</h2>
        <p>
          Every One starts at Spark. As what you build gives back time, money and effort, the committee moves
          you up: Spark, Glow, Flame, Blaze, White heat, Blue flame and Star.
        </p>
        <p>
          <Link href="/share">Share an idea</Link>
        </p>
      </section>
    </>
  );
}
