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

import Link from "next/link";

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
export const FAN_FLY = "(width > 640px) and (prefers-reduced-motion: no-preference)";
/** JS moves (the phone row's glide, the tilt) only where motion is allowed outright, as the CSS does (F-MOTION.reduced):
 * a browser that matches neither this nor "reduce" stays still too. */
export const FAN_MOVES = "(prefers-reduced-motion: no-preference)";
/** The pointer tilt needs a pointer that hovers and is fine: never on touch (C-ONES-FAN.behaviour/6). */
export const FAN_FINE = "(hover: hover) and (pointer: fine)";
/** Home.dc.html's timings: a card flies for 0.8s, 45ms after the one before it; the side panel is gone after 0.4s. */
export const FAN_MOTION = { flyMs: 800, staggerMs: 45, sideMs: 400 } as const;

const holds = (query: string) =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia(query).matches;

const cardsIn = (view: HTMLElement) => [
  ...view.querySelectorAll<HTMLElement>(":scope > .fan-track > .fan-card"),
];

/** The phone row's scroll position that puts each card at its snap point, from layout positions only: offsetLeft
 * ignores transforms, so a track still gliding back from its desktop translateX, or a card's own pose, never skews
 * it. The first card sits at the start of the track, which sits at the view's padding edge. */
function snapPoints(view: HTMLElement): number[] {
  const items = cardsIn(view);
  const first = items[0];
  if (!first) return [];
  const css = getComputedStyle(view);
  const inset = (parseFloat(css.paddingLeft) || 0) - (parseFloat(css.scrollPaddingLeft) || 0);
  return items.map((card) => Math.max(0, card.offsetLeft - first.offsetLeft + inset));
}

/** The card the phone row rests on: the one whose snap point is nearest the scroll position (the last card when the
 * row is scrolled to its end, as the last card cannot reach its snap point). */
function restingCard(view: HTMLElement): number {
  let best = 0;
  let gap = Infinity;
  snapPoints(view).forEach((left, i) => {
    const d = Math.abs(left - view.scrollLeft);
    if (d < gap) {
      gap = d;
      best = i;
    }
  });
  return best;
}

/**
 * C-ONES-FAN: the posts from the Ones as a fan of cards on the dark slab (lane D; Home.dc.html `.ofan`, BLD-D020).
 *
 * - **None:** the `empty` node ("No Ones yet. …").
 * - **One:** the post and the companion card side by side, both in the reading order; "Post 1 of 1". On a phone the
 *   row scrolls by swipe with snap.
 * - **Several:** stacked at rest, the first card facing you and up to three behind it, offset and darker, with the
 *   side panel ("6 fixes, 6 people", See details). The first interaction (a click, focus, an arrow, the wheel, a swipe
 *   or See details) spreads it into a row 12px apart, and the side panel fades and slides out. Previous and Next, ←
 *   and →, a sideways swipe and the wheel move one card at a time; at either end the wheel hands the scroll back to
 *   the page, so the page never gets stuck (C-ONES-FAN.behaviour/4). "Post 1 of 4" says where you are. Only the
 *   current card is in the reading order; when it leaves with focus inside it, focus moves on to Next (Previous at the
 *   last card). On a phone there is no stack: the row is the view's own scroll with snap. A swipe or a fling moves
 *   it natively; Previous, Next, ← → and the wheel scroll it to the next card's snap point, a quick second press going
 *   one card further; and the line, the reading order and the buttons follow the card the row settles on, once per
 *   settle (C-ONES-FAN.behaviour/7).
 *
 * Motion (BLD-D026; the rules are in motion.css, the look in components.css): the first spread flies the cards out
 * of the stack into the row, each 45ms after the one before; with a fine pointer, hovering the stack opens it a
 * little and the cards tilt toward the pointer; Cheer pops once on the person's own press. Unless motion is allowed
 * outright (`FAN_MOVES`), nothing flies, tilts, glides or pops: the cards take their poses at once (F-MOTION.reduced).
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
  const spreadOnce = useRef(false);
  // The card the line names, for the listeners; and on a phone, the card a Previous, Next, arrow or wheel scroll is
  // heading for until the row settles. A finger on the row clears it: the person has taken over.
  const atNow = useRef(0);
  const pending = useRef<number | null>(null);
  const tiltOn = useRef(false);
  const view = useRef<HTMLDivElement>(null);
  const side = useRef<HTMLDivElement>(null);
  const next = useRef<HTMLButtonElement>(null);
  const prev = useRef<HTMLButtonElement>(null);
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

  // Every change of card comes through here. Focus never stays in a card that leaves the reading order: it moves on
  // to Next, or to Previous at the last card, before the card turns inert (WCAG 2.4.3)
  const moveTo = useCallback(
    (n: number) => {
      const from = atNow.current;
      if (n !== from) {
        const out = view.current ? cardsIn(view.current)[from] : undefined;
        if (out && out.contains(document.activeElement)) (n >= count - 1 ? prev : next).current?.focus();
        atNow.current = n;
      }
      setAt(n);
    },
    [count],
  );

  // On a phone the row is the view's own scroll: bring card n to its snap point. False when nothing will scroll
  const snapTo = useCallback((n: number, instant: boolean) => {
    const el = view.current;
    const left = el ? snapPoints(el)[n] : undefined;
    if (!el || left === undefined || typeof el.scrollTo !== "function") return false;
    if (Math.abs(left - el.scrollLeft) < 1) return false;
    el.scrollTo({ left, behavior: instant ? "auto" : "smooth" });
    return true;
  }, []);

  const go = useCallback(
    (to: number) => {
      if (count < 2) return;
      const n = Math.min(Math.max(to, 0), count - 1);
      spreadOut();
      if (!holds(FAN_PHONE)) {
        pending.current = null;
        moveTo(n);
        return;
      }
      // On a phone the line changes when the row settles, once; without a glide the jump is instant, so it changes
      // at once and the settle that follows agrees with it
      const glide = holds(FAN_MOVES);
      pending.current = n;
      if (!glide) moveTo(n);
      if (!snapTo(n, !glide)) {
        pending.current = null;
        moveTo(n);
      }
    },
    [count, moveTo, snapTo, spreadOut],
  );

  // One card on from where the phone row is heading, so a quick second Next goes two cards on, never back. Wider
  // than a phone there is no scroll to head anywhere: one card on from the line's
  const step = useCallback(
    (d: 1 | -1) =>
      go(((holds(FAN_PHONE) ? pending.current : null) ?? Math.min(atNow.current, count - 1)) + d),
    [count, go],
  );

  // The fly-out and the side panel's exit end on the board's timings; nothing is left running after them
  useEffect(() => {
    if (!sideOut) return;
    const t = setTimeout(() => setSideOut(false), FAN_MOTION.sideMs);
    return () => clearTimeout(t);
  }, [sideOut]);

  useEffect(() => {
    if (!fly) return;
    const t = setTimeout(
      () => setFly(false),
      FAN_MOTION.flyMs + Math.max(count - 1, 0) * FAN_MOTION.staggerMs + 50,
    );
    return () => clearTimeout(t);
  }, [fly, count]);

  // On a phone the row settles where a button or the person left it, and the line, the reading order and Previous
  // and Next follow that card, once per settle: on scrollend, or where a browser has no scrollend, once the row has
  // been still for 120ms. Only a scroll of the row runs this, so nothing runs while it is still or off-screen.
  useEffect(() => {
    const el = view.current;
    if (!el || count < 2) return;
    let quiet: ReturnType<typeof setTimeout> | undefined;
    const settle = () => {
      clearTimeout(quiet);
      if (!holds(FAN_PHONE)) return;
      const i = restingCard(el);
      pending.current = null;
      if (i > 0) spreadOut();
      moveTo(i);
    };
    const onScroll = () => {
      clearTimeout(quiet);
      quiet = setTimeout(settle, 120);
    };
    const ends = "onscrollend" in window;
    el.addEventListener("scrollend", settle);
    if (!ends) el.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      clearTimeout(quiet);
      el.removeEventListener("scrollend", settle);
      el.removeEventListener("scroll", onScroll);
    };
  }, [count, moveTo, spreadOut]);

  // Turned to a phone's width (a window narrowed, a phone rotated), the row jumps to the card the line names, one
  // frame later, once layout has the phone's rules. The jump is instant, so the row has landed by the next line; if
  // nothing scrolled, the line follows where the row rests instead, so the card on screen is never the inert one.
  // Turned wider, a scroll heading somewhere is dropped.
  useEffect(() => {
    if (count < 2 || typeof window.matchMedia !== "function") return;
    const m = window.matchMedia(FAN_PHONE);
    let frame = 0;
    const onChange = () => {
      pending.current = null;
      cancelAnimationFrame(frame);
      if (!m.matches) return;
      frame = requestAnimationFrame(() => {
        const el = view.current;
        if (!el || !m.matches) return;
        snapTo(Math.min(atNow.current, count - 1), true);
        const i = restingCard(el);
        if (i > 0) spreadOut();
        moveTo(i);
      });
    };
    m.addEventListener("change", onChange);
    return () => {
      cancelAnimationFrame(frame);
      m.removeEventListener("change", onChange);
    };
  }, [count, moveTo, snapTo, spreadOut]);

  // The wheel steps one card per gesture while there is a card to go to; otherwise the page scrolls on.
  useEffect(() => {
    const el = view.current;
    if (!el || count < 2) return;
    const onWheel = (e: WheelEvent) => {
      const delta = Math.abs(e.deltaY) >= Math.abs(e.deltaX) ? e.deltaY : e.deltaX;
      if (Math.abs(delta) < 4) {
        pending.current = null; // the browser scrolls this one: the person has taken over
        return;
      }
      const forward = delta > 0;
      // A phone's row has no stack to open: the first step already moves a card
      if (!spread && !holds(FAN_PHONE)) {
        if (!forward) return;
        e.preventDefault();
        spreadOut();
        lastWheel.current = Date.now();
        return;
      }
      const from = (holds(FAN_PHONE) ? pending.current : null) ?? cur;
      const can = forward ? from < count - 1 : from > 0;
      if (!can) return;
      e.preventDefault();
      if (Date.now() - lastWheel.current < 380) return;
      lastWheel.current = Date.now();
      step(forward ? 1 : -1);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [cur, count, spread, spreadOut, step]);

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
      step(1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      step(-1);
    }
  };

  // The tilt follows a mouse that hovers with a fine pointer, never a finger, and only with motion allowed
  const tiltIn = (e: PointerEvent<HTMLDivElement>) => {
    tiltOn.current = e.pointerType === "mouse" && holds(FAN_FINE) && holds(FAN_MOVES);
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
    moveTo(0);
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
            pending.current = null; // a finger or the pointer on the row: the person has taken over
            swipe.current = { x: e.clientX, y: e.clientY };
          }}
          onTouchStart={() => {
            pending.current = null;
          }}
          onPointerUp={(e) => {
            const s = swipe.current;
            swipe.current = null;
            // On a phone a finger scrolls the row natively; only a mouse drag steps it here
            if (!s || !several || (holds(FAN_PHONE) && e.pointerType !== "mouse")) return;
            const dx = e.clientX - s.x;
            if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(e.clientY - s.y)) step(dx < 0 ? 1 : -1);
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
              ref={prev}
              className="round-btn"
              aria-label="Previous post"
              aria-disabled={cur === 0 ? true : undefined}
              onClick={() => step(-1)}
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
              onClick={() => step(1)}
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
