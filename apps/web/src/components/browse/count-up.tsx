"use client";

import { useEffect, useRef, useState } from "react";

import { reducedMotion } from "@/lib/motion/flip";

/** The digits of a figure as it is shown ("58,600", "₹24", "930"), with what goes before and after them. */
function parts(value: string): { pre: string; n: number; post: string; grouped: boolean } | null {
  const m = /^(\D*)([\d,]+)(\D*)$/.exec(value);
  if (!m) return null;
  const n = Number(m[2]!.replace(/,/g, ""));
  if (!Number.isFinite(n)) return null;
  return { pre: m[1]!, n, post: m[3]!, grouped: m[2]!.includes(",") };
}

/**
 * A count or a big figure that counts up once, the first time it comes into view (S-WALL.rules/3). The page renders
 * the final figure, so it reads right with no script; a screen reader always gets the final figure, never a
 * figure mid-count. Reduced motion: the figure simply stands (F-MOTION.reduced).
 */
export function CountUp({ value, ms = 900 }: { value: string; ms?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  // The figure mid-count; null shows the figure itself
  const [counting, setCounting] = useState<string | null>(null);
  const done = useRef(false);

  useEffect(() => {
    const p = parts(value);
    const el = ref.current;
    if (
      !p ||
      p.n === 0 ||
      done.current ||
      !el ||
      reducedMotion() ||
      typeof IntersectionObserver === "undefined"
    ) {
      return;
    }
    let raf = 0;
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        io.disconnect();
        done.current = true;
        const start = performance.now();
        const fmt = (x: number) => `${p.pre}${p.grouped ? x.toLocaleString("en-IN") : String(x)}${p.post}`;
        const tick = (now: number) => {
          const t = Math.min(1, (now - start) / ms);
          const eased = 1 - Math.pow(1 - t, 3);
          setCounting(fmt(Math.round(p.n * eased)));
          if (t < 1) raf = requestAnimationFrame(tick);
          else setCounting(null);
        };
        raf = requestAnimationFrame(tick);
      },
      { threshold: 0.4 },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [value, ms]);

  return (
    <span ref={ref}>
      <span aria-hidden="true">{counting ?? value}</span>
      <span className="vh">{value}</span>
    </span>
  );
}
