"use client";

import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

/**
 * C-CREW-DECK, the motion and controls (lane D; the cards' content and order are lane F's, L-CREW). All cards sit
 * in one pile; only the front card and the edge of the next show. Next lifts the front card out to the right with a
 * slight tilt and tucks it behind the pile (620 ms); Previous brings the last card back out and lands it on top.
 * Round Previous and Next buttons, pager dots with the current one as a short bar, the position in words, and ← →
 * while focus is in the deck (F-A11Y.rules/11). With reduced motion the cards swap without the flight. Only the
 * front card is in the reading order.
 */
export function Deck({
  label,
  noun = "Idea",
  cards,
  index,
  onIndexChange,
}: {
  /** The region's name ("Ideas close to yours"). */
  label: string;
  /** "Idea 1 of 5". */
  noun?: string;
  /** One node per card, each a full card. */
  cards: ReactNode[];
  index: number;
  onIndexChange: (index: number) => void;
}) {
  const count = cards.length;
  const at = Math.min(Math.max(index, 0), Math.max(count - 1, 0));
  const [motion, setMotion] = useState<{ from: number; dir: "next" | "prev" } | null>(null);
  const timer = useRef<number | null>(null);
  const front = useRef<HTMLDivElement | null>(null);

  useEffect(
    () => () => {
      if (timer.current) window.clearTimeout(timer.current);
    },
    [],
  );

  const go = (to: number) => {
    if (to < 0 || to >= count || to === at) return;
    setMotion({ from: at, dir: to > at ? "next" : "prev" });
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setMotion(null), 640);
    onIndexChange(to);
  };

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const t = e.target as HTMLElement;
    if (t.closest("input, textarea, select, [contenteditable='true']")) return;
    if (e.key === "ArrowRight") {
      e.preventDefault();
      go(at + 1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      go(at - 1);
    }
  };

  return (
    <div className="deck-wrap" role="region" aria-label={label} onKeyDown={onKey}>
      <div className="deck">
        <div className="deck-track">
          {cards.map((card, i) => {
            const cls =
              i === at
                ? motion?.dir === "prev"
                  ? "dcard cur fromback"
                  : "dcard cur"
                : motion?.dir === "next" && i === motion.from
                  ? "dcard toback"
                  : i === at + 1
                    ? "dcard nx"
                    : "dcard";
            return (
              <div
                key={i}
                ref={i === at ? front : undefined}
                className={cls}
                aria-hidden={i === at ? undefined : true}
                inert={i === at ? undefined : true}
              >
                {card}
              </div>
            );
          })}
        </div>
      </div>
      <div className="deck-ctl">
        <button
          type="button"
          className="round-btn deck-b"
          aria-label={`Previous ${noun.toLowerCase()}`}
          aria-disabled={at === 0 ? true : undefined}
          onClick={() => go(at - 1)}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="m15 5-7 7 7 7" />
          </svg>
        </button>
        <span className="deck-dots" aria-hidden="true">
          {cards.map((_, i) => (
            <i key={i} className={i === at ? "on" : undefined} />
          ))}
        </span>
        <button
          type="button"
          className="round-btn deck-b"
          aria-label={`Next ${noun.toLowerCase()}`}
          aria-disabled={at >= count - 1 ? true : undefined}
          onClick={() => go(at + 1)}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="m9 5 7 7-7 7" />
          </svg>
        </button>
        <span className="vh" aria-live="polite">
          {count ? `${noun} ${at + 1} of ${count}` : ""}
        </span>
      </div>
    </div>
  );
}
