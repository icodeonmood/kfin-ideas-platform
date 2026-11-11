"use client";

/**
 * "What the Ones are up to" on the home page (DEC-072), on a Zed band with drifting light behind the Ones' jerseys
 * (DEC-099). Manual by default: it moves only when someone presses Next, Previous or Play. While playing it stops
 * on hover or focus, and it never plays under reduced motion (WCAG 2.2.2). The strip scrolls inside itself; the
 * page never scrolls sideways.
 */
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { jerseyProps, OneCardBody } from "@/components/one-card";
import type { PublicOne } from "@/server/ones";

const STEP_MS = 8000;
const QUERY = "(prefers-reduced-motion: reduce)";

function useReducedMotion() {
  return useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia(QUERY);
      m.addEventListener("change", cb);
      return () => m.removeEventListener("change", cb);
    },
    () => window.matchMedia(QUERY).matches,
    () => false,
  );
}

function Glyph({ d, fill = false }: { d: string; fill?: boolean }) {
  return (
    <svg
      className={fill ? "glyph glyph-fill" : "glyph"}
      viewBox="0 0 20 20"
      aria-hidden="true"
      focusable="false"
    >
      <path d={d} />
    </svg>
  );
}

export function OnesCarousel({ ones }: { ones: PublicOne[] }) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [held, setHeld] = useState(false);
  const [moved, setMoved] = useState(false);
  const reduced = useReducedMotion();
  const strip = useRef<HTMLDivElement>(null);
  const n = ones.length;

  useEffect(() => {
    if (!playing || held || reduced || n < 2) return;
    const t = window.setInterval(() => setIndex((i) => (i + 1) % n), STEP_MS);
    return () => window.clearInterval(t);
  }, [playing, held, reduced, n]);

  useEffect(() => {
    const el = strip.current;
    const card = el?.querySelectorAll<HTMLElement>(":scope > ul > li")[index];
    if (el && card)
      el.scrollTo({ left: card.offsetLeft - el.offsetLeft, behavior: reduced ? "auto" : "smooth" });
  }, [index, reduced]);

  if (!n) return null;
  const go = (d: number) => {
    setMoved(true);
    setIndex((i) => (i + d + n) % n);
  };
  return (
    <section
      className="band stage ones-carousel"
      data-theme="zed"
      data-glow="1"
      aria-roledescription="carousel"
      aria-labelledby="oc-title"
    >
      <div className="band-inner ones-carousel-inner">
        <div className="ones-carousel-head">
          <div className="ones-carousel-title">
            <h2 id="oc-title" className="t-display">
              What the Ones are up to
            </h2>
            <p className="muted">Colleagues building what they noticed. Yours could be next.</p>
          </div>
          <div className="ones-carousel-controls">
            {!reduced && n > 1 ? (
              <button
                type="button"
                className="round-btn"
                aria-label={playing ? "Pause the carousel" : "Play the carousel"}
                onClick={() => setPlaying((p) => !p)}
              >
                {playing ? <Glyph d="M7.5 5v10M12.5 5v10" /> : <Glyph d="M7 5v10l8-5z" fill />}
              </button>
            ) : null}
            <button
              type="button"
              className="round-btn"
              aria-label="Previous One"
              data-refract="22"
              onClick={() => go(-1)}
            >
              <Glyph d="M12.5 4.5 7 10l5.5 5.5" />
            </button>
            <button
              type="button"
              className="round-btn"
              aria-label="Next One"
              data-refract="22"
              onClick={() => go(1)}
            >
              <Glyph d="M7.5 4.5 13 10l-5.5 5.5" />
            </button>
          </div>
        </div>
        {/* The strip scrolls sideways, so it takes keyboard focus too (arrow keys scroll it). */}
        <div
          ref={strip}
          className="strip ones-strip"
          role="region"
          aria-label="The Ones, card by card"
          tabIndex={0}
          onMouseEnter={() => setHeld(true)}
          onMouseLeave={() => setHeld(false)}
          onFocus={() => setHeld(true)}
          onBlur={() => setHeld(false)}
        >
          <ul aria-live={playing ? "off" : "polite"}>
            {ones.map((o, i) => (
              <li
                key={o.number}
                {...jerseyProps(o)}
                aria-roledescription="slide"
                aria-label={`${i + 1} of ${n}`}
                aria-current={moved && i === index ? "true" : undefined}
              >
                <OneCardBody one={o} />
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
