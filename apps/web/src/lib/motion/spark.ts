/**
 * The 1% spark (F-MOTION.inside): a burst of small slashes from the button that made a commitment. It marks only
 * sending an idea, sending a team-up request, sending answers and sending a decision; never an ordinary click.
 * Drawn on the effects layer (#mo-fx), never interactive, and not at all with reduced motion. Values from the pack's
 * own engine (reference/css/motion-engine.js `burst`).
 */
import { reducedMotion } from "./flip";

const COLOURS = ["#395DED", "#F46835", "#8964E7", "#12B76A", "#F8B348", "#E25798"];
const EASE_OUT = "cubic-bezier(.16,1,.3,1)";

/** Where each slash flies: an even spread round the circle with a little jitter, 46 to 116 px out. */
export function sparkPaths(n: number, random: () => number = Math.random) {
  return Array.from({ length: n }, (_, i) => {
    const angle = (i / n) * Math.PI * 2 + random() * 0.5;
    const distance = 46 + random() * 70;
    return {
      dx: Math.cos(angle) * distance,
      dy: Math.sin(angle) * distance,
      deg: (angle * 180) / Math.PI + 90,
      duration: 760 + random() * 360,
      colour: COLOURS[i % COLOURS.length]!,
    };
  });
}

function layer(): HTMLElement | null {
  return document.getElementById("mo-fx");
}

/** Burst from the middle of `from` (a button), or from a point. */
export function sparkBurst(from: Element | { x: number; y: number }, n = 18): void {
  if (typeof document === "undefined" || reducedMotion()) return;
  const fx = layer();
  if (!fx) return;
  let x: number;
  let y: number;
  if ("getBoundingClientRect" in from) {
    const r = from.getBoundingClientRect();
    x = r.left + r.width / 2;
    y = r.top + r.height / 2;
  } else {
    ({ x, y } = from);
  }

  const wave = document.createElement("i");
  wave.className = "mo-wave";
  fx.appendChild(wave);
  wave
    .animate(
      [
        { transform: `translate(${x}px, ${y}px) scale(1)`, opacity: 0.9 },
        { transform: `translate(${x}px, ${y}px) scale(9)`, opacity: 0 },
      ],
      { duration: 700, easing: EASE_OUT, fill: "forwards" },
    )
    .finished.then(
      () => wave.remove(),
      () => wave.remove(),
    );

  for (const p of sparkPaths(n)) {
    const s = document.createElement("i");
    s.className = "mo-spark";
    s.style.background = p.colour;
    fx.appendChild(s);
    s.animate(
      [
        { transform: `translate(${x}px, ${y}px) rotate(${p.deg}deg) scale(.4)`, opacity: 1 },
        {
          transform: `translate(${x + p.dx * 0.8}px, ${y + p.dy * 0.8}px) rotate(${p.deg}deg) scale(1)`,
          opacity: 1,
          offset: 0.45,
        },
        {
          transform: `translate(${x + p.dx}px, ${y + p.dy + 26}px) rotate(${p.deg + 40}deg) scale(.2)`,
          opacity: 0,
        },
      ],
      { duration: p.duration, easing: EASE_OUT, fill: "forwards" },
    ).finished.then(
      () => s.remove(),
      () => s.remove(),
    );
  }
}
