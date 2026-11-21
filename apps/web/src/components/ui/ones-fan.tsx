"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
} from "react";

import Link from "next/link";

import { reducedMotion } from "@/lib/motion/flip";

import { Avatar } from "./avatar";

/** C-ONES-FAN's own words, as `reference/copy/Home.md` has them (the Ones block, the side panel and the card). */
export const ONES_FAN_COPY = {
  /** "6 fixes, 6 people": the posts, and the Ones behind them (a One may post more than once). */
  side: (fixes: number, people: number) =>
    `${fixes} ${fixes === 1 ? "fix" : "fixes"}, ${people} ${people === 1 ? "person" : "people"}`,
  sideBody: "Each one started with someone saying what kept going wrong. See them side by side.",
  sideButton: "See details",
  position: (at: number, of: number) => `Post ${at} of ${of}`,
  shipped: "Shipped",
  thread: "Read the thread",
} as const;

/** PhoneHome's row: the cards scroll natively with snap (the same width as the CSS's phone rules). */
export const FAN_PHONE = "(max-width: 640px)";
/** The fly-out plays only where there is a stack to fly out of and motion is allowed (F-MOTION.reduced). */
export const FAN_FLY = "(min-width: 641px) and (prefers-reduced-motion: no-preference)";
/** The pointer tilt needs a pointer that hovers and is fine: never on touch (C-ONES-FAN.behaviour/6). */
export const FAN_FINE = "(hover: hover) and (pointer: fine)";
/** Home.dc.html's timings: a card flies for 0.8s, 45ms after the one before it; the side panel is gone after 0.4s. */
export const FAN_MOTION = { flyMs: 800, staggerMs: 45, sideMs: 400 } as const;

const holds = (query: string) =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia(query).matches;

function onPhoneChange(cb: () => void) {
  if (typeof window.matchMedia !== "function") return () => undefined;
  const m = window.matchMedia(FAN_PHONE);
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
}

/** Whether the fan is drawn as PhoneHome's row; false on the server and wherever the width cannot be read. */
function usePhoneRow(): boolean {
  return useSyncExternalStore(
    onPhoneChange,
    () => holds(FAN_PHONE),
    () => false,
  );
}

/**
 * C-ONES-FAN: the posts from the Ones as a fan of cards on the dark slab (lane D; Home.dc.html `.ofan`, BLD-D020).
 *
 * - **None:** the `empty` node ("No Ones yet. …").
 * - **One:** the post and the companion card side by side, both in the reading order; "Post 1 of 1". On a phone the
 *   row scrolls by swipe with snap.
 * - **Several:** stacked at rest, the first card facing you and up to three behind it, offset and darker, with the
 *   side panel ("6 fixes, 6 people", See details). The first interaction (a click, focus, an arrow, the wheel, a swipe
 *   or See details) spreads it into a row 12px apart and the side panel goes. Previous and Next, ← and →, a sideways
 *   swipe and the wheel move one card at a time; at either end the wheel hands the scroll back to the page, so the
 *   page never gets stuck (C-ONES-FAN.behaviour/4). "Post 1 of 4" says where you are. Only the front card is in the
 *   reading order. On a phone the row shows at rest and a swipe moves one card.
 *
 * Static in this slot: the stack's angled pose and the row's angled edge are drawn, not animated, and under reduced
 * motion the stack is a flat offset. The fly out, cheerPop and the spread glide come with the motion slot.
 */
export function OnesFan({
  label = "Posts from the Ones",
  cards,
  empty,
  companion,
  people,
}: {
  label?: string;
  cards: ReactNode[];
  /** "No Ones yet. …" (C-ONES-FAN.states). */
  empty: ReactNode;
  /** With one post, the companion card: "The next One could be you. …" (`OnesNext`). */
  companion: ReactNode;
  /** How many Ones posted these, for the side panel's "N people"; one each when not given. */
  people?: number;
}) {
  const count = cards.length;
  const several = count > 1;
  const shown = several ? cards : [...cards, companion];
  const [at, setAt] = useState(0);
  const [spread, setSpread] = useState(false);
  // The fly-out playing (the region's data-fly), and the side panel on its way out: both only with motion allowed
  const [fly, setFly] = useState(false);
  const [sideOut, setSideOut] = useState(false);
  const phone = usePhoneRow();
  const spreadOnce = useRef(false);
  const tiltOn = useRef(false);
  const view = useRef<HTMLDivElement>(null);
  const side = useRef<HTMLDivElement>(null);
  const next = useRef<HTMLButtonElement>(null);
  const focusNext = useRef(false);
  const lastWheel = useRef(0);
  const swipe = useRef<{ x: number; y: number } | null>(null);
  const cur = Math.min(at, Math.max(count - 1, 0));

  // Spreading takes the side panel away. Whatever spreads it (See details, an arrow key, the wheel or a swipe), if
  // focus was in the panel it moves on to Next rather than dropping to the page (WCAG 2.4.3).
  const spreadOut = useCallback(() => {
    if (side.current && side.current.contains(document.activeElement)) focusNext.current = true;
    if (!spreadOnce.current) {
      spreadOnce.current = true;
      const moving = holds(FAN_FLY);
      setFly(moving);
      setSideOut(moving);
    }
    setSpread(true);
  }, []);

  // On a phone the row is the view's own scroll: bring the card to its snap point (no glide under reduced motion)
  const snapTo = useCallback((n: number) => {
    const el = view.current;
    const card = el?.querySelectorAll<HTMLElement>(":scope > .fan-track > .fan-card")[n];
    if (!el || !card || typeof el.scrollTo !== "function") return;
    const pad = parseFloat(getComputedStyle(el).scrollPaddingLeft) || 0;
    const left = el.scrollLeft + card.getBoundingClientRect().left - el.getBoundingClientRect().left - pad;
    el.scrollTo({ left, behavior: reducedMotion() ? "auto" : "smooth" });
  }, []);

  const go = useCallback(
    (to: number) => {
      if (count < 2) return;
      const n = Math.min(Math.max(to, 0), count - 1);
      spreadOut();
      setAt(n);
      if (phone) snapTo(n);
    },
    [count, phone, snapTo, spreadOut],
  );

  // The fly-out and the side panel's exit end on the board's timings; nothing is left running after them
  useEffect(() => {
    if (!sideOut) return;
    const t = window.setTimeout(() => setSideOut(false), FAN_MOTION.sideMs);
    return () => window.clearTimeout(t);
  }, [sideOut]);

  useEffect(() => {
    if (!fly) return;
    const t = window.setTimeout(
      () => setFly(false),
      FAN_MOTION.flyMs + Math.max(count - 1, 0) * FAN_MOTION.staggerMs + 50,
    );
    return () => window.clearTimeout(t);
  }, [fly, count]);

  // On a phone the position line follows the card the row snapped to, however it got there (a swipe, a fling,
  // Previous or Next). The observer only reports changes, so nothing runs while the row is still or off-screen.
  useEffect(() => {
    const el = view.current;
    if (!phone || !el || count < 2 || typeof IntersectionObserver !== "function") return;
    const items = [...el.querySelectorAll<HTMLElement>(":scope > .fan-track > .fan-card")];
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          const i = items.indexOf(e.target as HTMLElement);
          if (i < 0 || !e.isIntersecting || e.intersectionRatio < 0.6) continue;
          if (i > 0) spreadOut();
          setAt(i);
        }
      },
      { root: el, threshold: 0.6 },
    );
    for (const c of items) io.observe(c);
    return () => io.disconnect();
  }, [phone, count, spreadOut]);

  // The wheel steps one card per gesture while there is a card to go to; otherwise the page scrolls on.
  useEffect(() => {
    const el = view.current;
    if (!el || count < 2) return;
    const onWheel = (e: WheelEvent) => {
      const delta = Math.abs(e.deltaY) >= Math.abs(e.deltaX) ? e.deltaY : e.deltaX;
      if (Math.abs(delta) < 4) return;
      const forward = delta > 0;
      // A phone's row has no stack to open: the first step already moves a card
      if (!spread && !phone) {
        if (!forward) return;
        e.preventDefault();
        spreadOut();
        lastWheel.current = Date.now();
        return;
      }
      const can = forward ? cur < count - 1 : cur > 0;
      if (!can) return;
      e.preventDefault();
      if (Date.now() - lastWheel.current < 380) return;
      lastWheel.current = Date.now();
      go(cur + (forward ? 1 : -1));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [cur, count, go, phone, spread, spreadOut]);

  // Once spread, focus that was in the side panel (or on See details) moves on to Next.
  useEffect(() => {
    if (spread && focusNext.current) {
      focusNext.current = false;
      next.current?.focus();
    }
  }, [spread]);

  if (count === 0) return <div className="fan-empty">{empty}</div>;

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!several) return;
    if (e.key === "ArrowRight") {
      e.preventDefault();
      go(cur + 1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      go(cur - 1);
    }
  };

  // The tilt follows a mouse that hovers with a fine pointer, never a finger, and never under reduced motion
  const tiltIn = (e: PointerEvent<HTMLDivElement>) => {
    tiltOn.current = e.pointerType === "mouse" && holds(FAN_FINE) && !reducedMotion();
  };
  const tilt = (e: PointerEvent<HTMLDivElement>) => {
    if (!tiltOn.current) return;
    const r = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    e.currentTarget.style.setProperty("--tx", `${(y * -4).toFixed(2)}deg`);
    e.currentTarget.style.setProperty("--ty", `${(x * 5).toFixed(2)}deg`);
  };

  const open = () => {
    focusNext.current = true;
    setAt(0);
    spreadOut();
  };

  const isSpread = several && spread;
  return (
    <div
      className={["fan", several ? "several" : "one", isSpread ? "spread" : ""].filter(Boolean).join(" ")}
      role="region"
      aria-label={label}
      data-fly={isSpread && fly ? "open" : undefined}
      style={{ ["--at" as string]: cur }}
      onKeyDown={onKey}
    >
      <div className="fan-stage">
        <div
          ref={view}
          className="fan-view"
          onFocusCapture={several ? spreadOut : undefined}
          onClick={several ? spreadOut : undefined}
          onPointerDown={(e) => {
            swipe.current = { x: e.clientX, y: e.clientY };
          }}
          onPointerUp={(e) => {
            const s = swipe.current;
            swipe.current = null;
            // On a phone a finger scrolls the row natively; only a mouse drag steps it here
            if (!s || !several || (phone && e.pointerType !== "mouse")) return;
            const dx = e.clientX - s.x;
            if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(e.clientY - s.y)) go(cur + (dx < 0 ? 1 : -1));
          }}
        >
          <div className="fan-track">
            {shown.map((card, i) => {
              const live = !several || i === cur;
              // Spread, the card coming up sits angled in at the row's edge and the ones after it further back
              const pose = isSpread && i - cur === 2 ? "edge" : isSpread && i - cur > 2 ? "far" : "";
              return (
                <div
                  key={i}
                  className={["fan-card", several && i === cur ? "cur" : "", pose].filter(Boolean).join(" ")}
                  style={{ ["--i" as string]: i }}
                  aria-hidden={live ? undefined : true}
                  inert={live ? undefined : true}
                  onPointerEnter={tiltIn}
                  onPointerMove={tilt}
                  onPointerLeave={(e) => {
                    e.currentTarget.style.removeProperty("--tx");
                    e.currentTarget.style.removeProperty("--ty");
                  }}
                >
                  {card}
                </div>
              );
            })}
          </div>
        </div>
        {several && (!spread || sideOut) ? (
          // Spread, the panel is on its way out (motion.css fades and slides it): out of the reading order at once
          <div
            ref={side}
            className="fan-side"
            data-leaving={spread ? "" : undefined}
            aria-hidden={spread ? true : undefined}
            inert={spread ? true : undefined}
          >
            <p className="fan-side-t">{ONES_FAN_COPY.side(count, people ?? count)}</p>
            <p className="fan-side-p">{ONES_FAN_COPY.sideBody}</p>
            <button type="button" className="opost-pill fan-side-b" onClick={open}>
              {ONES_FAN_COPY.sideButton}
            </button>
          </div>
        ) : null}
      </div>
      <div className="fan-ctl">
        <span className="fan-pos meta num" aria-live="polite">
          {ONES_FAN_COPY.position(cur + 1, count)}
        </span>
        {several ? (
          <>
            <button
              type="button"
              className="round-btn"
              aria-label="Previous post"
              aria-disabled={cur === 0 ? true : undefined}
              onClick={() => go(cur - 1)}
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
              ref={next}
              type="button"
              className="round-btn"
              aria-label="Next post"
              aria-disabled={cur >= count - 1 ? true : undefined}
              onClick={() => go(cur + 1)}
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
          </>
        ) : null}
      </div>
    </div>
  );
}

/**
 * C-ONES-FAN.card: a One's post on the dark slab, keyed by tier (Home.dc.html `.ocard`). Header: the avatar with its
 * tier ring, the name, "One No. 1, Tier 4, Blaze" and when. Body: the sentence, five lines at most. The media block:
 * the tier's two glows, "Shipped" and "Adopted by 3 teams", the big figure and its unit line. Footer: Cheer on the
 * left, a toggle named "Cheer Rohit Menon’s fix, 214 cheers" (reference/copy/Home.md) showing the count, and "Read
 * the thread" with the reply count on the right. The name shows only if the One agreed; otherwise the card says "One
 * No. 17" (the Ones' consent rule). Without `onCheer` the count is shown, not pressable. The tier's colours come from
 * the tokens (`--tier-N`, `--tier-N-ring`) through `data-tier`, never from a literal.
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
  cheers,
  cheered = false,
  onCheer,
  replies,
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
  cheers: number;
  /** This person has cheered it (the toggle shows pressed). */
  cheered?: boolean;
  onCheer?: () => void;
  replies: number;
  threadHref: string;
}) {
  // cheerPop plays once on the person's own press that turns Cheer on, never for a cheer already there on load
  const [popped, setPopped] = useState(false);
  const who = name ?? `One No. ${number}`;
  const cheerWords = `Cheer ${name ? `${name}’s` : `One No. ${number}’s`} fix, `;
  const count = (
    <>
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.9"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />
      </svg>
      <span className="num">{cheers}</span>
      <span className="vh"> {cheers === 1 ? "cheer" : "cheers"}</span>
    </>
  );
  return (
    <article className="opost" data-tier={tier}>
      <header className="opost-h">
        <Avatar initials={name ? initials : String(number)} size={44} tier={tier} className="opost-av" />
        <span className="opost-who">
          <b>{who}</b>
          <span>
            {name ? `One No. ${number}, ` : ""}Tier {tier}, {tierName}
          </span>
        </span>
        <span className="opost-ago">{ago}</span>
      </header>
      <p className="opost-s">{sentence}</p>
      <div className="opost-m">
        <span className="opost-tags">
          <span className="opost-tag ok">{ONES_FAN_COPY.shipped}</span>
          {adopted ? <span className="opost-tag">{adopted}</span> : null}
        </span>
        <div className="opost-fig">
          <p className="opost-big num">{figure}</p>
          <p className="opost-unit">{unit}</p>
        </div>
      </div>
      <footer className="opost-f">
        {onCheer ? (
          <button
            type="button"
            className={popped && cheered ? "opost-cheer on" : "opost-cheer"}
            aria-pressed={cheered}
            onClick={() => {
              setPopped(!cheered);
              onCheer();
            }}
          >
            <span className="vh">{cheerWords}</span>
            {count}
          </button>
        ) : (
          <span className="opost-cheer">{count}</span>
        )}
        <Link href={threadHref} className="opost-pill opost-t">
          {ONES_FAN_COPY.thread} <span className="num opost-n">{replies}</span>
        </Link>
      </footer>
    </article>
  );
}

/**
 * C-ONES-FAN.states, one post: the companion card beside it, an outline on the slab with a soft blue light
 * (Home.dc.html `.oc-next`): "The next One could be you", the line under it, and the way to share. The caller gives
 * the words (S-03's copy) and where the action goes.
 */
export function OnesNext({
  title,
  body,
  action,
  href,
}: {
  title: string;
  body: string;
  action: string;
  href: string;
}) {
  return (
    <article className="opost opost-next">
      <p className="opost-nt">{title}</p>
      <p className="opost-np">{body}</p>
      <Link href={href} className="opost-pill opost-t">
        {action}
      </Link>
    </article>
  );
}

/** C-ONES-FAN.states, none: "No Ones yet" and the line under it, on the slab (Home.dc.html `.o-empty`). */
export function OnesEmpty({ title, body }: { title: string; body: string }) {
  return (
    <div className="opost-empty">
      <p className="opost-et">{title}</p>
      <p className="opost-ep">{body}</p>
    </div>
  );
}
