"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type MouseEvent } from "react";
import { flushSync } from "react-dom";

import { CountUp } from "@/components/browse/count-up";
import { restoreRow, rowOffset, withBack } from "@/components/browse/return-to";
import "@/components/browse/browse.css";
import { Status } from "@/components/status";
import { Button, ButtonLink } from "@/components/ui/button";
import { ChoiceChips } from "@/components/ui/chips";
import { StatusPill } from "@/components/ui/pill";
import { Sorts } from "@/components/ui/sorts";
import type {
  EmberIssueView,
  ImpactResponse,
  JustInItem,
  JustInResponse,
  KindlingResponse,
  OneCardView,
  WallIdea,
} from "@/lib/contracts/api";
import type { Kind, WallSort } from "@/lib/contracts/enums";
import { flip, reducedMotion } from "@/lib/motion/flip";

import { DESK_STEP, PHONE_STEP, wallHref, type Part, type WallData, type WallState } from "./state";

/** Exact words: reference/copy/Wall.md (desktop) and PhoneWall.md (phone). Where the two differ, both are in the
 * page and the width shows one (`.wl-desk` / `.wl-phone`), so each reads exactly as its board. */
const KINDS: { value: Kind | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "problem", label: "Problems" },
  { value: "fix", label: "Fixes" },
  { value: "business_idea", label: "Business ideas" },
];
const SORTS: { value: WallSort; label: string }[] = [
  { value: "popular", label: "Popular" },
  { value: "newest", label: "Newest" },
  { value: "crew", label: "Crew size" },
  { value: "ones", label: "Ones" },
];
/** The phone's cycler goes newest, popular, crew size, Ones (S-WALL.phone). */
const PHONE_SORTS = ["newest", "popular", "crew", "ones"].map((v) => SORTS.find((o) => o.value === v)!);
const STAGE_NAME = { picked: "Picked", being_built: "Being built", shipped: "Shipped" } as const;
const LOAD_FAILED = "We can't load the wall just now. Please try again in a minute.";

/** A Kindling row's line on a phone: "Problem, Investor service. 4 colleagues on it" (PhoneWall.md). */
function phoneMeta(meta: string): string {
  return meta.replace(/, ([\d,]+ colleagues? on it)$/, ". $1");
}

/** "Show 5 more", "Show 2 more", "Show fewer" (L-WALL.justin/5), for `step` rows a page. */
function moreLabel(total: number, shown: number, step: number): string | null {
  if (shown < total) return `Show ${Math.min(step, total - shown)} more`;
  return total > step ? "Show fewer" : null;
}

const fmt = (n: number) => n.toLocaleString("en-IN");

/** A row's id on the page and in the address's `at`: the same idea can sit in Kindling and in Impact, so each
 * section prefixes its own ("kin-IDEA-2026-000123"); the way back finds the row in the section it was opened from. */
const rowId = (section: "kin" | "jin" | "imp", id: string) => `${section}-${id}`;

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(String(res.status));
  return (await res.json()) as T;
}

function Chevron() {
  return (
    <svg className="wl-chev" width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function WallScreen({ state, data }: { state: WallState; data: WallData }) {
  const router = useRouter();
  const root = useRef<HTMLDivElement>(null);
  const [st, setSt] = useState({ kind: state.kind, sort: state.sort, more: state.more, ones: state.ones });
  const [kin, setKin] = useState<Part<KindlingResponse>>(data.kindling);
  const [jin, setJin] = useState<Part<JustInResponse>>(data.justIn);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const asked = useRef(0);

  // The state lives in the URL (P-ROUTES.state): every change replaces the address, so Back leaves the Wall
  // instead of stepping through sorts, and a shared link reproduces the view.
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      // Arriving back from an idea: the row returns to where it sat, has focus and is washed once (J-BROWSE/5).
      if (state.at) {
        const at = state.at;
        requestAnimationFrame(() => restoreRow(root.current, at, state.dy));
      }
      if (state.at || state.dy !== null) window.history.replaceState(null, "", wallHref(st));
      return;
    }
    window.history.replaceState(null, "", wallHref(st));
  }, [st, state.at, state.dy]);

  const paused = [data.kindling, data.justIn].find((p) => !p.ok && p.paused !== null);
  if (paused && !paused.ok) {
    return (
      <div className="wl" ref={root}>
        <Top />
        <p className="paused paused-inline">{paused.paused}</p>
      </div>
    );
  }

  const justInUrl = (s: typeof st, offset: number, limit: number) => {
    const q = new URLSearchParams({ sort: s.sort, offset: String(offset), limit: String(limit) });
    if (s.kind !== "all") q.set("kind", s.kind);
    return `/api/wall/just-in?${q.toString()}`;
  };

  // A change that cannot load puts the chip, the sort and the address back to the view still on screen, so the
  // same choice can be made again to try again (S-WALL error state)
  const pickKind = async (value: string) => {
    const kind = value as Kind | "all";
    if (kind === st.kind) return;
    const was = st;
    const next = { ...st, kind, more: 0 };
    setSt(next);
    const n = ++asked.current;
    setBusy(true);
    try {
      const kq = kind === "all" ? "" : `?kind=${kind}`;
      const [k, j] = await Promise.all([
        getJson<KindlingResponse>(`/api/wall/kindling${kq}`),
        getJson<JustInResponse>(justInUrl(next, 0, DESK_STEP)),
      ]);
      if (n !== asked.current) return;
      setKin({ ok: true, data: k });
      setJin({ ok: true, data: j });
      setFailed(false);
    } catch {
      if (n === asked.current) {
        setSt(was);
        setFailed(true);
      }
    } finally {
      if (n === asked.current) setBusy(false);
    }
  };

  // Only the rows on screen: the other width's copy of each row is laid out nowhere, and would glide in from the
  // corner (S-WALL.rules/2)
  const rows = () =>
    Array.from(root.current?.querySelectorAll<HTMLElement>(".wl-jin [data-flip]") ?? []).filter(
      (el) => el.getClientRects().length > 0,
    );

  const pickSort = async (value: string) => {
    const sort = value as WallSort;
    if (sort === st.sort) return;
    const was = st;
    const next = { ...st, sort };
    setSt(next);
    const n = ++asked.current;
    setBusy(true);
    try {
      const j = await getJson<JustInResponse>(justInUrl(next, 0, DESK_STEP * (next.more + 1)));
      if (n !== asked.current) return;
      // Re-sorting glides every row to its new place (S-WALL.rules/2, V-ACC.browse/2); each row keeps its words
      await flip(rows, () => {
        flushSync(() => {
          setJin({ ok: true, data: j });
          setFailed(false);
        });
      });
    } catch {
      if (n === asked.current) {
        setSt(was);
        setFailed(true);
      }
    } finally {
      if (n === asked.current) setBusy(false);
    }
  };

  const showMore = async (step: number) => {
    if (!jin.ok) return;
    const total = jin.data.total;
    const shown = Math.min(step * (st.more + 1), total);
    if (shown >= total) {
      setSt({ ...st, more: 0 });
      return;
    }
    const more = st.more + 1;
    const need = Math.min(DESK_STEP * (more + 1), total);
    const have = jin.data.items.length;
    if (have < need) {
      const n = ++asked.current;
      setBusy(true);
      try {
        const page = await getJson<JustInResponse>(justInUrl(st, have, need - have));
        if (n !== asked.current) return;
        const seen = new Set(jin.data.items.map((i) => i.id));
        setJin({
          ok: true,
          data: { ...page, items: [...jin.data.items, ...page.items.filter((i) => !seen.has(i.id))] },
        });
        setFailed(false);
      } catch {
        if (n === asked.current) setFailed(true);
        return;
      } finally {
        if (n === asked.current) setBusy(false);
      }
    }
    flushSync(() => setSt({ ...st, more }));
    // Focus moves to the first row the button added, so a keyboard carries on where the new rows start
    const variant = step === PHONE_STEP ? ".wl-jp" : ".wl-jt";
    root.current?.querySelectorAll<HTMLElement>(`${variant} [data-row] a`)[shown]?.focus();
  };

  /** The Ones in leaderboard order (BLD-E020), in place: the state effect replaces the address, and the list comes
   * into view once it has rendered. */
  const showLeaderboard = () => {
    flushSync(() => setSt({ ...st, ones: "leaderboard" }));
    document
      .getElementById("ones")
      ?.scrollIntoView({ block: "start", behavior: reducedMotion() ? "auto" : "smooth" });
  };

  /** Opens an idea with the way back to this exact view: kind, sort, how far Just in is open, and the row. */
  const open = (e: MouseEvent<HTMLAnchorElement>, to: string, id: string) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    const here = wallHref(st, id, rowOffset(e.currentTarget));
    window.history.replaceState(null, "", here);
    router.push(withBack(to, here));
  };
  const back = wallHref(st);
  const linkTo = (to: string) => withBack(to, back);

  return (
    <div className="wl cine" ref={root}>
      <Top />

      <section id="kindling" className="wl-sec" aria-labelledby="wl-kin-h">
        <div className="wl-head">
          <h2 id="wl-kin-h" className="d2">
            Kindling
          </h2>
          <p className="body wl-desk">
            Every idea and problem shared at KFintech, and where it is now. Each one could catch.
          </p>
          <p className="body wl-phone">Every idea and problem shared, and where it is now.</p>
        </div>
        <div className="wl-chips">
          <ChoiceChips label="Show" options={KINDS} value={st.kind} onChange={pickKind} scroll />
        </div>
        {failed ? <Status kind="error" title={LOAD_FAILED} className="wl-fail" /> : null}
        <Kindling
          kin={kin}
          jin={jin}
          st={st}
          busy={busy}
          linkTo={linkTo}
          open={open}
          onSort={pickSort}
          onMore={showMore}
          onEverything={() => pickKind("all")}
        />
      </section>

      <Ones ones={data.ones} order={st.ones} onLeaderboard={showLeaderboard} />
      <ImpactSection impact={data.impact} linkTo={linkTo} open={open} />
      <EmberSection ember={data.ember} />

      <footer className="wl-foot">
        <p className="wl-foot-b">1% Club</p>
        <a href="#ember">The Ember</a>
        <p>A KFintech programme</p>
      </footer>
    </div>
  );
}

function Top() {
  return (
    <header className="wl-top">
      <div className="wl-top-row">
        <h1 className="d1 wl-title">Wall</h1>
        <p className="lead wl-desk">
          Every idea from across KFintech, the people behind what shipped, what it changed, and the Ember to
          round it up.
        </p>
        <p className="lead wl-phone">
          Every idea from across KFintech, the people behind what shipped, and what it changed.
        </p>
      </div>
      <nav aria-label="On the Wall" className="wl-secnav wl-desk">
        <a href="#kindling">
          <span className="wl-sn-n">01</span>
          <span className="wl-sn-t">Kindling</span>
          <span />
          <span className="wl-sn-s">Every idea and problem</span>
        </a>
        <a href="#recognition">
          <span className="wl-sn-n">02</span>
          <span className="wl-sn-t">Recognition</span>
          <span />
          <span className="wl-sn-s">The Ones</span>
        </a>
        <a href="#impact">
          <span className="wl-sn-n">03</span>
          <span className="wl-sn-t">Impact</span>
          <span />
          <span className="wl-sn-s">What shipped ideas changed</span>
        </a>
        <a href="#ember">
          <span className="wl-sn-n">04</span>
          <span className="wl-sn-t">The Ember</span>
          <span />
          <span className="wl-sn-s">The newsletter</span>
        </a>
      </nav>
    </header>
  );
}

type Opener = (e: MouseEvent<HTMLAnchorElement>, to: string, id: string) => void;

function Kindling({
  kin,
  jin,
  st,
  busy,
  linkTo,
  open,
  onSort,
  onMore,
  onEverything,
}: {
  kin: Part<KindlingResponse>;
  jin: Part<JustInResponse>;
  st: { kind: Kind | "all"; sort: WallSort; more: number };
  busy: boolean;
  linkTo: (to: string) => string;
  open: Opener;
  onSort: (v: string) => void;
  onMore: (step: number) => void;
  onEverything: () => void;
}) {
  if (!kin.ok && !jin.ok) return <Status kind="error" title={LOAD_FAILED} className="wl-fail" />;
  const nothing =
    st.kind !== "all" && kin.ok && jin.ok && jin.data.total === 0 && kin.data.every((s) => s.count === 0);
  return (
    <div className="wl-kin" aria-busy={busy || undefined}>
      {nothing ? (
        <div className="wl-none wl-phone">
          <p>Nothing here for this filter yet</p>
          <Button variant="line" size="sm" onClick={onEverything}>
            Show everything
          </Button>
        </div>
      ) : null}
      {kin.ok ? (
        <div className="wl-stages">
          {kin.data.map((s) => (
            <section key={s.stage} className="card wl-stage" aria-labelledby={`wl-st-${s.stage}`}>
              <div className="wl-st-h">
                <span className="wl-desk" aria-hidden="true">
                  <StatusPill status={s.stage} />
                </span>
                <h3 id={`wl-st-${s.stage}`} className="wl-st-name">
                  {STAGE_NAME[s.stage]}
                </h3>
                <span className="fig wl-st-n">
                  <CountUp value={String(s.count)} />
                </span>
              </div>
              {s.items.length ? (
                <ul className="wl-rows">
                  {s.items.map((it) => (
                    <KindlingRow key={it.id} it={it} linkTo={linkTo} open={open} />
                  ))}
                </ul>
              ) : null}
            </section>
          ))}
        </div>
      ) : (
        <Status kind="error" title={LOAD_FAILED} className="wl-fail" />
      )}
      {jin.ok ? (
        <JustIn jin={jin.data} st={st} linkTo={linkTo} open={open} onSort={onSort} onMore={onMore} />
      ) : (
        <Status kind="error" title={LOAD_FAILED} className="wl-fail" />
      )}
    </div>
  );
}

function KindlingRow({ it, linkTo, open }: { it: WallIdea; linkTo: (to: string) => string; open: Opener }) {
  const href = linkTo(it.to);
  const row = rowId("kin", it.id);
  return (
    <li className="wl-row" data-handover="expand" data-row={row}>
      <h4 className="wl-rt wl-desk">
        <Link href={href} onClick={(e) => open(e, it.to, row)}>
          {it.title}
        </Link>
      </h4>
      <p className="wl-rm wl-desk">{it.meta}</p>
      <Link href={href} className="wl-prow wl-phone" onClick={(e) => open(e, it.to, row)}>
        <span className="wl-pmain">
          <span className="wl-pt">{it.title}</span>
          <span className="wl-pm">{phoneMeta(it.meta)}</span>
        </span>
        <Chevron />
      </Link>
    </li>
  );
}

const COLUMN: Record<WallSort, number> = { popular: 0, newest: 1, crew: 2, ones: 3 };

function JustIn({
  jin,
  st,
  linkTo,
  open,
  onSort,
  onMore,
}: {
  jin: JustInResponse;
  st: { sort: WallSort; more: number };
  linkTo: (to: string) => string;
  open: Opener;
  onSort: (v: string) => void;
  onMore: (step: number) => void;
}) {
  const on = COLUMN[st.sort];
  const cls = (i: number) => (i === on ? "wl-jv on" : "wl-jv");
  const desk = jin.items.slice(0, DESK_STEP * (st.more + 1));
  const phone = jin.items.slice(0, PHONE_STEP * (st.more + 1));
  const deskMore = moreLabel(jin.total, desk.length, DESK_STEP);
  const phoneMore = moreLabel(jin.total, phone.length, PHONE_STEP);
  const fig = (it: JustInItem) => [
    fmt(it.opened_7d),
    it.shared_label,
    fmt(it.crew_count),
    fmt(it.ones_count),
  ];
  return (
    <section className="wl-jin" aria-labelledby="wl-jin-h">
      <div className="wl-jhead">
        <div className="wl-jtitle">
          <h3 id="wl-jin-h" className="wl-jh">
            Just in
          </h3>
          <p className="wl-jsub wl-desk">{jin.sub}</p>
          <span className="wl-jcount wl-phone">{fmt(jin.total)}</span>
        </div>
        {jin.total > 0 ? (
          <>
            <div className="wl-desk">
              <Sorts options={SORTS} value={st.sort} onChange={onSort} />
            </div>
            <div className="wl-phone">
              <Sorts options={PHONE_SORTS} value={st.sort} onChange={onSort} />
            </div>
          </>
        ) : null}
      </div>
      {jin.total === 0 ? (
        <p className="wl-jnone">Nothing of this kind with the review desk right now.</p>
      ) : (
        <>
          <div className="wl-jt wl-desk">
            <div className="wl-jrow wl-jhd" aria-hidden="true">
              <p>Idea</p>
              {["Opened this week", "Shared", "Crew", "Ones"].map((t, i) => (
                <p key={t} className={cls(i)}>
                  {t}
                </p>
              ))}
            </div>
            <ul className="wl-jlist" aria-label="Just in, with the review desk">
              {desk.map((it) => {
                const f = fig(it);
                return (
                  <li
                    key={it.id}
                    className="wl-jrow"
                    data-handover="expand"
                    data-row={rowId("jin", it.id)}
                    data-flip={it.id}
                  >
                    <div>
                      <h4 className="wl-jtt">
                        <Link href={linkTo(it.to)} onClick={(e) => open(e, it.to, rowId("jin", it.id))}>
                          {it.title}
                        </Link>
                      </h4>
                      <p className="wl-jk">{it.meta}</p>
                    </div>
                    <p className={cls(0)}>
                      <span className="vh">Opened this week: </span>
                      {f[0]}
                    </p>
                    <p className={cls(1)}>
                      <span className="vh">Shared: </span>
                      {f[1]}
                    </p>
                    <p className={cls(2)}>
                      <span className="vh">Crew: </span>
                      {f[2]}
                    </p>
                    <p className={cls(3)}>
                      <span className="vh">Ones on the crew: </span>
                      {f[3]}
                    </p>
                  </li>
                );
              })}
            </ul>
            {deskMore ? (
              <div className="wl-jmore">
                <Button variant="line" onClick={() => onMore(DESK_STEP)}>
                  {deskMore}
                </Button>
              </div>
            ) : null}
          </div>
          <div className="wl-jp wl-phone">
            <ul className="wl-rows" aria-label="Just in, with the review desk">
              {phone.map((it) => (
                <li
                  key={it.id}
                  className="wl-row"
                  data-handover="expand"
                  data-row={rowId("jin", it.id)}
                  data-flip={it.id}
                >
                  <Link
                    href={linkTo(it.to)}
                    className="wl-prow"
                    onClick={(e) => open(e, it.to, rowId("jin", it.id))}
                  >
                    <span className="wl-pmain">
                      <span className="wl-pt">{it.title}</span>
                      <span className="wl-pm">
                        {it.meta}. {it.figure_label}
                      </span>
                    </span>
                    <Chevron />
                  </Link>
                </li>
              ))}
            </ul>
            {phoneMore ? (
              <Button variant="text" className="wl-pmore" onClick={() => onMore(PHONE_STEP)}>
                {phoneMore}
              </Button>
            ) : null}
          </div>
        </>
      )}
    </section>
  );
}

/** A One who hides their name from the Wall is shown by number (BLD-E013). */
// NOT DRAWN (BLD-E044): HR sign-off
const hiddenOneName = (n: number) => `One No. ${n}`;

/** One card per One (L-WALL.ones): an article in the list, so each card reads as one item with its number, name, tier
 * and brief (J-ONE/3). */
function OneCard({ one }: { one: OneCardView }) {
  return (
    <li className="wl-one-li">
      <article className="jersey wl-one" data-tier={String(Math.min(7, Math.max(1, one.tier)))}>
        <div className="wl-one-top">
          <span className="jersey-bar" aria-hidden="true" />
          <span className="wl-one-flag">{one.flag_label}</span>
        </div>
        <p className="fig wl-one-no">
          <span className="vh">Number </span>
          {one.number}
        </p>
        <h3 className="wl-one-name">{one.person?.name ?? hiddenOneName(one.number)}</h3>
        <p className="wl-one-tier">{one.tier_label}</p>
        {one.brief ? <p className="wl-one-brief">{one.brief}</p> : null}
      </article>
    </li>
  );
}

/** The Wall shows the five newest Ones, newest first, so a new One shows there (J-ONE.3, BLD-E050); the leaderboard
 * shows every One by tier, then hours saved (BLD-E020). The worker sends the wall order oldest first. */
const ONES_ON_WALL = 5;

function Ones({
  ones,
  order,
  onLeaderboard,
}: {
  ones: Part<OneCardView[]>;
  order: "wall" | "leaderboard";
  onLeaderboard: () => void;
}) {
  if (!ones.ok && ones.paused !== null) return null;
  const list = ones.ok
    ? order === "leaderboard"
      ? ones.data
      : ones.data.slice(-ONES_ON_WALL).reverse()
    : [];
  return (
    <section id="recognition" className="wl-sec" aria-labelledby="wl-ones-h">
      <div className="slab wl-slab">
        <div className="wl-slab-head">
          <h2 id="wl-ones-h" className="d2">
            The Ones
          </h2>
          <p className="wl-slab-lead wl-desk">
            Colleagues whose ideas shipped and made a measured difference. Each One keeps a number, and their
            tier warms as their impact grows.
          </p>
          <p className="wl-slab-lead wl-phone">
            Colleagues whose fixes shipped and made a measured difference. Each keeps a number.
          </p>
        </div>
        {ones.ok ? (
          list.length ? (
            // On a phone the cards scroll sideways inside the slab, so the list takes focus for the keyboard
            <ul id="ones" className="wl-ones" tabIndex={0} aria-label="The Ones">
              {list.map((o) => (
                <OneCard key={o.number} one={o} />
              ))}
            </ul>
          ) : null
        ) : (
          <p className="wl-slab-lead">{LOAD_FAILED}</p>
        )}
        {ones.ok && order === "wall" && ones.data.length > 0 ? (
          <p className="wl-slab-link">
            {/* Wall.md: the link is "#ones". The leaderboard opens in place: the order goes in the address without a
                new history entry, and the list scrolls into view (a link without script still lands on #ones) */}
            <a
              href="#ones"
              onClick={(e) => {
                if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
                  return;
                e.preventDefault();
                onLeaderboard();
              }}
            >
              The Ones leaderboard
            </a>
          </p>
        ) : null}
      </div>
    </section>
  );
}

const DOT: Record<string, string> = { "90d": "ok", "30d": "warn", pending: "off" };

function ImpactSection({
  impact,
  linkTo,
  open,
}: {
  impact: Part<ImpactResponse>;
  linkTo: (to: string) => string;
  open: Opener;
}) {
  if (!impact.ok && impact.paused !== null) return null;
  return (
    <section id="impact" className="wl-sec" aria-labelledby="wl-imp-h">
      <div className="wl-head">
        <h2 id="wl-imp-h" className="d2 wl-imp-h">
          <span className="wl-desk">What shipped ideas have changed so far.</span>
          <span className="wl-phone">What shipped ideas changed</span>
        </h2>
        <p className="body wl-desk">
          Measured 30 and 90 days after each idea ships, and confirmed by Finance where money is involved.
        </p>
        <p className="body wl-phone">
          Measured 30 and 90 days after each fix ships. Finance confirms anything about money.
        </p>
      </div>
      {impact.ok ? (
        <>
          <ul className="wl-tiles">
            {impact.data.tiles.map((t) => (
              <li key={t.key} className="wl-tile">
                <p className="fig wl-tbig">
                  <CountUp value={t.value} />
                  {t.suffix ? <span className="wl-tsuf"> {t.suffix}</span> : null}
                </p>
                <p className="wl-tlabel">{t.label}</p>
              </li>
            ))}
          </ul>
          {impact.data.live.length ? (
            // The live-fixes table (S-WALL.impact, L-WALL.impact/2): four columns, a row per live fix. ARIA table
            // roles keep the grid rows the CSS lays out, and the header row names each cell's column.
            <div className="wl-live wl-desk" role="table" aria-label="Live fixes and their measured change">
              <div role="rowgroup">
                <div className="wl-trow wl-thd" role="row">
                  <p role="columnheader">Live fix</p>
                  <p role="columnheader">Measured change</p>
                  <p role="columnheader">Measured</p>
                  <p role="columnheader">Team that runs it</p>
                </div>
              </div>
              <div role="rowgroup">
                {impact.data.live.map((l) => {
                  const to = `/ideas/${encodeURIComponent(l.id)}?from=wall`;
                  return (
                    <div
                      key={l.id}
                      role="row"
                      className="wl-trow"
                      data-handover="expand"
                      data-row={rowId("imp", l.id)}
                    >
                      <p role="cell" className="wl-lw">
                        <Link href={linkTo(to)} onClick={(e) => open(e, to, rowId("imp", l.id))}>
                          {l.what}
                        </Link>
                      </p>
                      <p role="cell" className="wl-lc">
                        {l.change}
                      </p>
                      <p role="cell" className="wl-lm">
                        <span className={`wl-dot ${DOT[l.measured] ?? "off"}`} aria-hidden="true" />
                        {l.measured_label}
                      </p>
                      <p role="cell" className="wl-lm">
                        {l.team}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}
          <p className="wl-note wl-desk">
            Already running elsewhere? Team up from its page to bring a live fix to your area.
          </p>
        </>
      ) : (
        <Status kind="error" title={LOAD_FAILED} className="wl-fail" />
      )}
    </section>
  );
}

function IssueLatest({ issue }: { issue: EmberIssueView }) {
  return (
    <article className="card wl-issue">
      <div className="wl-issue-top">
        <p className="wl-eb">
          Issue {issue.number}, {issue.month}
        </p>
        <span className="pill band">Latest</span>
      </div>
      {issue.headline ? <h3 className="wl-issue-h">{issue.headline}</h3> : null}
      {issue.items.length ? (
        <ol className="wl-issue-items">
          {issue.items.map((t, i) => (
            <li key={t}>
              <span>{String(i + 1).padStart(2, "0")}</span>
              <p>{t}</p>
            </li>
          ))}
        </ol>
      ) : null}
      {issue.to ? (
        <div className="wl-issue-a">
          <ButtonLink href={issue.to}>Read this issue</ButtonLink>
        </div>
      ) : null}
    </article>
  );
}

function EmberSection({ ember }: { ember: Part<EmberIssueView[]> }) {
  if (!ember.ok && ember.paused !== null) return null;
  const latest = ember.ok ? ember.data.filter((i) => i.state === "latest") : [];
  const soon = ember.ok ? ember.data.filter((i) => i.state === "coming_soon") : [];
  return (
    <section id="ember" className="wl-sec" aria-labelledby="wl-emb-h">
      <h2 id="wl-emb-h" className="d2">
        The Ember
      </h2>
      <p className="body wl-emb-lead">
        The 1% Club&apos;s newsletter: what caught, who built it, and what it changed.
      </p>
      {ember.ok ? (
        <div className={latest.length ? "wl-emb" : "wl-emb solo"}>
          {latest.map((i) => (
            <IssueLatest key={i.number} issue={i} />
          ))}
          <div className="wl-emb-side">
            {soon.map((i) => (
              <div key={i.number} className="placeholder wl-soon">
                <span className="pill soon">Coming soon</span>
                <p className="wl-soon-t">
                  Issue {i.number}, {i.month}
                </p>
                {i.headline ? <p className="body">{i.headline}</p> : null}
              </div>
            ))}
            <div className="card wl-inbox">
              <p className="wl-inbox-t">Every issue lands in your inbox too.</p>
              <p className="body">Read the Ember here or in your work email.</p>
            </div>
          </div>
        </div>
      ) : (
        <Status kind="error" title={LOAD_FAILED} className="wl-fail" />
      )}
    </section>
  );
}
