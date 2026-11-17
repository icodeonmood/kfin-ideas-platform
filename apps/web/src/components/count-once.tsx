"use client";

import { useEffect, useRef, useState } from "react";

import { reducedMotion } from "@/lib/motion/flip";

/** The digits of a figure as shown ("620", "₹18", "58,600", "₹6.2"), with what comes before and after them. */
export function figureParts(
  value: string,
): { pre: string; n: number; post: string; grouped: boolean; decimals: number } | null {
  const m = /^(\D*?)(\d[\d,]*(?:\.\d+)?)(\D*)$/.exec(value);
  if (!m) return null;
  const digits = m[2]!;
  const n = Number(digits.replace(/,/g, ""));
  if (!Number.isFinite(n)) return null;
  const decimals = digits.includes(".") ? digits.split(".")[1]!.length : 0;
  return { pre: m[1]!, n, post: m[3]!, grouped: digits.includes(","), decimals };
}

/**
 * A big figure that counts up once, the first time it comes into view (F-MOTION.arrive/5: a One's figures on S-ONE,
 * points on S-H6). The page renders the final figure, so it reads right with no script and before it is in view.
 * While it counts, the moving digits are hidden from a screen reader, which hears the final figure; afterwards the
 * figure is plain text. Reduced motion: the figure simply stands (F-MOTION/4).
 */
export function CountOnce({ value, ms = 900 }: { value: string; ms?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [counting, setCounting] = useState<string | null>(null);
  const done = useRef(false);

  useEffect(() => {
    const p = figureParts(value);
    const el = ref.current;
    if (
      !p ||
      p.n === 0 ||
      done.current ||
      !el ||
      reducedMotion() ||
      typeof IntersectionObserver === "undefined"
    )
      return;
    let raf = 0;
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        io.disconnect();
        done.current = true;
        const start = performance.now();
        const fmt = (x: number) => {
          const fixed = x.toFixed(p.decimals);
          const shown = p.grouped
            ? Number(fixed).toLocaleString("en-IN", { minimumFractionDigits: p.decimals })
            : fixed;
          return `${p.pre}${shown}${p.post}`;
        };
        const tick = (now: number) => {
          const t = Math.min(1, (now - start) / ms);
          const eased = 1 - Math.pow(1 - t, 3);
          if (t < 1) {
            setCounting(fmt(p.n * eased));
            raf = requestAnimationFrame(tick);
          } else {
            setCounting(null);
          }
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
      {counting === null ? (
        value
      ) : (
        <>
          <span aria-hidden="true">{counting}</span>
          <span className="vh">{value}</span>
        </>
      )}
    </span>
  );
}
