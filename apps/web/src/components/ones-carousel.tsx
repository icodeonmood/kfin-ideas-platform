"use client";

/**
 * "What the Ones are up to" on the home page (DEC-072). Manual by default: it moves only when someone presses
 * Next, Previous or Play. While playing it stops on hover or focus, and it never plays under reduced motion
 * (WCAG 2.2.2).
 */
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { OneCardBody } from "@/components/one-card";
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

export function OnesCarousel({ ones }: { ones: PublicOne[] }) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [held, setHeld] = useState(false);
  const [moved, setMoved] = useState(false);
  const reduced = useReducedMotion();
  const list = useRef<HTMLUListElement>(null);
  const n = ones.length;

  useEffect(() => {
    if (!playing || held || reduced || n < 2) return;
    const t = window.setInterval(() => setIndex((i) => (i + 1) % n), STEP_MS);
    return () => window.clearInterval(t);
  }, [playing, held, reduced, n]);

  useEffect(() => {
    const el = list.current;
    const card = el?.children[index] as HTMLElement | undefined;
    if (el && card)
      el.scrollTo({ left: card.offsetLeft - el.offsetLeft, behavior: reduced ? "auto" : "smooth" });
  }, [index, reduced]);

  if (!n) return null;
  const go = (d: number) => {
    setMoved(true);
    setIndex((i) => (i + d + n) % n);
  };
  return (
    <section className="ones-carousel" aria-roledescription="carousel" aria-labelledby="oc-title">
      <div className="ones-carousel-head">
        <div>
          <h2 id="oc-title">What the Ones are up to</h2>
          <p className="lead-dark">Colleagues building what they noticed. Yours could be next.</p>
        </div>
        <div className="carousel-controls">
          {!reduced && n > 1 ? (
            <button
              type="button"
              className="round-button"
              aria-label={playing ? "Pause the carousel" : "Play the carousel"}
              onClick={() => setPlaying((p) => !p)}
            >
              {playing ? (
                <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                  <rect x="2" y="1" width="3.5" height="12" />
                  <rect x="8.5" y="1" width="3.5" height="12" />
                </svg>
              ) : (
                <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                  <polygon points="3,1 13,7 3,13" />
                </svg>
              )}
            </button>
          ) : null}
          <button type="button" className="round-button" aria-label="Previous One" onClick={() => go(-1)}>
            <svg
              aria-hidden="true"
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <polyline points="10,3 5,8 10,13" />
            </svg>
          </button>
          <button type="button" className="round-button" aria-label="Next One" onClick={() => go(1)}>
            <svg
              aria-hidden="true"
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <polyline points="6,3 11,8 6,13" />
            </svg>
          </button>
        </div>
      </div>
      <ul
        ref={list}
        className="ones-strip"
        aria-live={playing ? "off" : "polite"}
        onMouseEnter={() => setHeld(true)}
        onMouseLeave={() => setHeld(false)}
        onFocus={() => setHeld(true)}
        onBlur={() => setHeld(false)}
      >
        {ones.map((o, i) => (
          <li
            key={o.number}
            className="one-card"
            aria-roledescription="slide"
            aria-label={`${i + 1} of ${n}`}
            aria-current={moved && i === index ? "true" : undefined}
          >
            <OneCardBody one={o} />
          </li>
        ))}
      </ul>
    </section>
  );
}
