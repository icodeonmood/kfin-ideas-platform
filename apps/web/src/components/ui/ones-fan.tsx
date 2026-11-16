"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
} from "react";

import { reducedMotion } from "@/lib/motion/flip";

import { Avatar } from "./avatar";
import { Pill } from "./pill";

/**
 * C-ONES-FAN: the posts from the Ones as a fan of cards (lane D). Stacked at rest, the first on top and the rest
 * peeking; the first interaction (a click, focus, an arrow, the wheel or a swipe) spreads it into a row 12px apart.
 * Previous and Next, ← and →, a sideways swipe, and the wheel move one card at a time; at either end the wheel hands
 * the scroll back to the page, so the page never gets stuck (C-ONES-FAN.behaviour/4). "Post 1 of 4" says where you
 * are. With reduced motion, cards move without gliding and do not tilt. Only the front card is in the reading order.
 */
export function OnesFan({
  label = "Posts from the Ones",
  cards,
  empty,
  companion,
}: {
  label?: string;
  cards: ReactNode[];
  /** "No Ones yet. …" (C-ONES-FAN.states). */
  empty: ReactNode;
  /** With one post, the companion card: "The next One could be you. …". */
  companion: ReactNode;
}) {
  const shown = cards.length === 1 ? [...cards, companion] : cards;
  const count = shown.length;
  const [at, setAt] = useState(0);
  const [spread, setSpread] = useState(false);
  const view = useRef<HTMLDivElement>(null);
  const lastWheel = useRef(0);
  const swipe = useRef<{ x: number; y: number } | null>(null);

  const go = useCallback(
    (to: number) => {
      setSpread(true);
      setAt(Math.min(Math.max(to, 0), count - 1));
    },
    [count],
  );

  // The wheel steps one card per gesture while there is a card to go to; otherwise the page scrolls on.
  useEffect(() => {
    const el = view.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      const delta = Math.abs(e.deltaY) >= Math.abs(e.deltaX) ? e.deltaY : e.deltaX;
      if (Math.abs(delta) < 4) return;
      const forward = delta > 0;
      if (!spread) {
        if (!forward) return;
        e.preventDefault();
        setSpread(true);
        lastWheel.current = Date.now();
        return;
      }
      const can = forward ? at < count - 1 : at > 0;
      if (!can) return;
      e.preventDefault();
      if (Date.now() - lastWheel.current < 380) return;
      lastWheel.current = Date.now();
      setAt((a) => a + (forward ? 1 : -1));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [at, count, spread]);

  if (cards.length === 0) return <div className="fan-empty">{empty}</div>;

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowRight") {
      e.preventDefault();
      go(at + 1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      go(at - 1);
    }
  };

  const tilt = (e: PointerEvent<HTMLDivElement>) => {
    if (reducedMotion() || e.pointerType !== "mouse") return;
    const r = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    e.currentTarget.style.setProperty("--tx", `${(y * -4).toFixed(2)}deg`);
    e.currentTarget.style.setProperty("--ty", `${(x * 5).toFixed(2)}deg`);
  };

  return (
    <div className="fan" role="region" aria-label={label} onKeyDown={onKey}>
      <div
        ref={view}
        className={spread ? "fan-view spread" : "fan-view"}
        style={{ ["--at" as string]: at }}
        onFocusCapture={() => setSpread(true)}
        onClick={() => setSpread(true)}
        onPointerDown={(e) => {
          swipe.current = { x: e.clientX, y: e.clientY };
        }}
        onPointerUp={(e) => {
          const s = swipe.current;
          swipe.current = null;
          if (!s) return;
          const dx = e.clientX - s.x;
          if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(e.clientY - s.y)) go(at + (dx < 0 ? 1 : -1));
        }}
      >
        <div className="fan-track">
          {shown.map((card, i) => (
            <div
              key={i}
              className={i === at ? "fan-card cur" : "fan-card"}
              style={{ ["--i" as string]: i, ["--d" as string]: i - at }}
              aria-hidden={i === at ? undefined : true}
              inert={i === at ? undefined : true}
              onPointerMove={tilt}
              onPointerLeave={(e) => {
                e.currentTarget.style.removeProperty("--tx");
                e.currentTarget.style.removeProperty("--ty");
              }}
            >
              {card}
            </div>
          ))}
        </div>
      </div>
      <div className="fan-ctl">
        <span className="fan-pos meta num" aria-live="polite">
          Post {at + 1} of {count}
        </span>
        <button
          type="button"
          className="round-btn"
          aria-label="Previous post"
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
        <button
          type="button"
          className="round-btn"
          aria-label="Next post"
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
      </div>
    </div>
  );
}

/**
 * C-ONES-FAN.card: a One's post on the dark slab, lit by their tier. The name shows only if the One agreed; otherwise
 * the card says "One No. 17" (the Ones' consent rule).
 */
export function OnesPost({
  name,
  initials,
  number,
  tier,
  tierName,
  ago,
  sentence,
  adopted,
  figure,
  unit,
  likes,
  comments,
  threadHref,
}: {
  name: string | null;
  initials: string;
  number: number;
  tier: number;
  tierName: string;
  /** "2d". */
  ago: string;
  sentence: string;
  /** "Adopted by 3 teams". */
  adopted?: string;
  figure: string;
  unit: string;
  likes: number;
  comments: number;
  threadHref: string;
}) {
  const who = name ?? `One No. ${number}`;
  return (
    <article className="opost" data-tier={tier}>
      <header className="opost-h">
        <Avatar initials={name ? initials : String(number)} size={44} tier={tier} />
        <span className="opost-who">
          <b>{who}</b>
          <span>
            One No. {number}, Tier {tier}, {tierName}
          </span>
        </span>
        <span className="opost-ago">{ago}</span>
      </header>
      <p className="opost-s">{sentence}</p>
      <div className="opost-pills">
        <Pill variant="band">Shipped</Pill>
        {adopted ? <span className="opost-adopt">{adopted}</span> : null}
      </div>
      <p className="opost-fig">
        <span className="fig num">{figure}</span>
        <span className="opost-unit">{unit}</span>
      </p>
      <footer className="opost-f">
        <span className="num">{likes} likes</span>
        <a href={threadHref} className="opost-t">
          Read the thread
        </a>
        <span className="num">{comments} comments</span>
      </footer>
    </article>
  );
}
