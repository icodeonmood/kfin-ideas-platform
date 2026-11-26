"use client";

/**
 * S-H2, Find your crew (lane F; L-CREW, C-CREW-DECK data, BLD-F030 to BLD-F037).
 *
 * Ideas close to yours, one card at a time, from `GET /api/crew`. Lane D's `Deck` draws the pile and its controls;
 * this screen gives it the cards and decides what Next and Previous mean here:
 * - Next passes the front card (`POST /api/crew/pass`), and on the last card ends the deck ("That's everyone for
 *   now"); a card the person has just asked about is not passed, Next only moves on. After a reload a requested
 *   card is passed like any other (BLD-F094); the request stays.
 * - Previous brings back the card passed just before (`POST /api/crew/pass/undo`).
 * - "Undo last pass" and "See them again" in the side card (L-CREW/6).
 * - The card's title opens lane C's preview (C-PREVIEW); its primary button and the card's "Team up" open lane F's
 *   team-up sheet. After a send the card reads "Requested", greyed and inactive, with "Withdraw" under it (DEC-126,
 *   `RequestedAction`); when the sheet closes ("Keep looking") it flies to the end of the deck and the next card
 *   comes to the front (S-H2.rules/3; with reduced motion it just moves). The server keeps it there, last, after a
 *   reload. "Withdraw" turns it back to "Team up" where it stands. The request joins "Your crews" as "Waiting for
 *   {lead}" and leaves it on a withdraw.
 * - Filters (L-CREW/5): a glass dialog "Filter ideas" with live counts; "Show N ideas" applies; the filters in use
 *   show as removable chips above the deck.
 *
 * Privacy (non-negotiable 7): cards carry only what the API's CrewCard carries, already masked; nothing else about
 * anyone's idea is fetched. Nothing typed or shown here is logged.
 */
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type JSX,
  type KeyboardEvent,
  type TouchEvent,
} from "react";

import { IdeaPreviewDialog } from "@/components/preview/idea-preview";
import { PhoneBar } from "@/components/shell/phone";
import { REQUESTED_COPY, RequestedAction } from "@/components/teamup/requested-action";
import { teamUpOpener, useTeamUpSheet, type TeamUpSent } from "@/components/teamup/teamup-sheet";
import { CrewFaces } from "@/components/ui/avatar";
import { Button, ButtonLink, buttonClass } from "@/components/ui/button";
import { MultiChips } from "@/components/ui/chips";
import { Deck } from "@/components/ui/deck";
import { Empty } from "@/components/ui/empty";
import { IDEA_STATUS, Pill, type PillVariant } from "@/components/ui/pill";
import type {
  CrewCard,
  CrewDeckResponse,
  CrewFilterGroup,
  CrewFilterKey,
  CrewPassResponse,
  CrewResetResponse,
  CrewUndoResponse,
  YourCrew,
} from "@/lib/contracts";

import "./crew.css";

// ---------------------------------------------------------------------------------------------------------------
// Words (reference/copy/Crew.md, C-CREW-DECK.states; lines the pack does not draw are in docs/hr-wording/lane-f.md, "Find your crew")
// ---------------------------------------------------------------------------------------------------------------
const plural = (n: number, one: string, many: string) => (n === 1 ? `1 ${one}` : `${n} ${many}`);

export const CREW_COPY = {
  title: "Find your crew",
  lead: "Ideas close to yours. Team up, or pass.",
  home: "Home",
  filters: "Filters",
  count: (n: number) => `${plural(n, "idea", "ideas")} close to yours`,
  deckLabel: "Ideas close to yours",
  problem: "The problem, in their words",
  lookingFor: "They're looking for",
  teamUp: "Team up",
  teamUpOn: (title: string, first: string) => `Team up on ${title}: send ${first} a note`,
  preview: (title: string) => `${title}. Preview the idea`,
  waiting: (first: string) => `Waiting for ${first}`,
  shared: "Shared",
  filterTitle: "Filter ideas",
  closeFilters: "Close filters",
  clearAll: "Clear all",
  show: (n: number) => `Show ${plural(n, "idea", "ideas")}`,
  matches: (n: number) => (n === 1 ? "1 idea matches" : `${n} ideas match`),
  removeFilter: (label: string) => `Remove filter: ${label}`,
  crews: "Your crews",
  crewsEmpty: "Ideas you team up on show here.",
  nonePassed: "None passed",
  passed: (n: number) => `${n} passed`,
  undo: "Undo last pass",
  allCrews: "All your crews in My ideas",
  leadLine: (name: string, area?: string | null) => (area ? `${name}, ${area}` : name),
  onCrew: "On the crew",
  /** What a screen reader hears after the title in a "Your crews" row ("…, waiting for Ravi. Open the idea."). */
  crewRowRest: (row: Pick<YourCrew, "state" | "label">) =>
    row.state === "waiting"
      ? `, ${row.label.charAt(0).toLowerCase()}${row.label.slice(1)}. Open the idea.`
      : ", you’re on the crew. Open the idea.",
  crewRow: (title: string, row: Pick<YourCrew, "state" | "label">) => `${title}${CREW_COPY.crewRowRest(row)}`,
  nothingTitle: "No crews to join yet",
  nothingBody:
    "We look for ideas close to the problems you've shared. Share one and we'll show you people working on the same thing, or browse the Wall for ideas you can help with.",
  browseWall: "Browse the Wall",
  endTitle: "That's everyone for now",
  endBody: (asked: number) =>
    asked > 0
      ? `You asked to team up on ${plural(asked, "idea", "ideas")}. New ideas close to yours show up here.`
      : "New ideas close to yours show up here.",
  seeAgain: "See them again",
  noneMatchTitle: "No ideas match these filters",
  noneMatchBody: "Try fewer filters, or clear them to see every idea close to yours.",
  loading: "Loading ideas close to yours",
  failedTitle: "These ideas did not load",
  failedBody: "Check your connection, then try again.",
  retry: "Try again",
  actionFailed: "That did not go through. Check your connection, then try again.",
} as const;

// ---------------------------------------------------------------------------------------------------------------
// The API (A-API.team-up `GET /crew` and the passes, through lane F's web handlers)
// ---------------------------------------------------------------------------------------------------------------
export type Filters = Partial<Record<CrewFilterKey, string[]>>;
export const FILTER_ORDER: readonly CrewFilterKey[] = [
  "location",
  "category",
  "status",
  "team_size",
  "looking_for",
];

/** `/api/crew?location=Hyderabad&location=Pune…`, keys in the panel's order, values as given. */
export function crewUrl(filters: Filters): string {
  const qs = new URLSearchParams();
  for (const key of FILTER_ORDER) for (const v of filters[key] ?? []) if (v) qs.append(key, v);
  const s = qs.toString();
  return s ? `/api/crew?${s}` : "/api/crew";
}

/** The filters in use, from the API's echo of them. */
export function filtersFrom(active: CrewDeckResponse["active"]): Filters {
  const out: Filters = {};
  for (const a of active) (out[a.key] ??= []).push(a.value);
  return out;
}

export function filterCount(filters: Filters): number {
  return FILTER_ORDER.reduce((n, k) => n + (filters[k]?.length ?? 0), 0);
}

const STATUS = IDEA_STATUS as Record<string, { label: string; pill: PillVariant } | undefined>;

/**
 * How a card names its lead in a sentence: their first name, or "the lead" when they hid their name from the Wall
 * or have left (the API sends "A colleague" with no initials, BLD-F042).
 */
export function leadFirst(lead: { first_name: string; initials: string }): string {
  return lead.initials ? lead.first_name : "the lead";
}

/** The card's status pill: a just-shared idea reads "Shared" here (BLD-F030). */
export function statusLabel(status: string): string {
  return status === "checking" ? CREW_COPY.shared : (STATUS[status]?.label ?? status);
}

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    cache: "no-store",
    headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}) },
    ...init,
  });
  if (!res.ok) throw new Error(String(res.status));
  return (await res.json()) as T;
}

const post = <T,>(url: string, body?: unknown) =>
  getJson<T>(url, { method: "POST", body: JSON.stringify(body ?? {}) });

// ---------------------------------------------------------------------------------------------------------------
// One card (C-CREW-DECK.card)
// ---------------------------------------------------------------------------------------------------------------
function Spark() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <path d="M8 20 16 4" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}

function TeamUpIcon() {
  return (
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
      focusable="false"
    >
      <circle cx="9" cy="8" r="4" />
      <path d="M2 21c0-3.9 3.1-7 7-7s7 3.1 7 7M19 8v6M16 11h6" />
    </svg>
  );
}

const noop = () => {};

/** Whether the person asked for less motion (F-MOTION): then a card asked about moves without its flight. */
function reducedMotion(): boolean {
  return (
    typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true
  );
}

function CardView({
  card,
  front,
  ghost = false,
  onPreview,
  onTeamUp,
  onWithdrawn,
  titleRef,
}: {
  card: CrewCard;
  front: boolean;
  /** The copy that flies to the back of the pile after a request (DEC-126): drawn only, none of it reachable. */
  ghost?: boolean;
  onPreview(): void;
  onTeamUp(): void;
  /** After "Withdraw" under "Requested" (DEC-126). */
  onWithdrawn(sent: TeamUpSent): void;
  titleRef?: (el: HTMLButtonElement | null) => void;
}) {
  const id = useId();
  const status = STATUS[card.status];
  return (
    <article className="crew-card" aria-labelledby={`${id}-t`}>
      <div className={`crew-top hue${card.hue === 2 ? 2 : 1}`}>
        <Pill variant={status?.pill ?? "blue"}>{statusLabel(card.status)}</Pill>
        <h2 className="crew-t" id={`${id}-t`}>
          <button
            type="button"
            className="crew-tb"
            ref={front ? titleRef : undefined}
            aria-label={CREW_COPY.preview(card.title)}
            onClick={onPreview}
          >
            {card.title}
          </button>
        </h2>
        <p className="crew-m">{[card.area, card.city].filter(Boolean).join(", ")}</p>
      </div>
      <p className="crew-why">
        <Spark />
        <span>{card.reason}</span>
      </p>
      <div className="crew-q">
        <p className="crew-l">{CREW_COPY.problem}</p>
        <p className="crew-a">{card.in_their_words}</p>
        {card.looking_for ? (
          <>
            <p className="crew-l">{CREW_COPY.lookingFor}</p>
            <p className="crew-a">{card.looking_for}</p>
          </>
        ) : null}
      </div>
      <div className="crew-foot">
        <CrewFaces
          people={card.crew_faces.map((p) => ({ name: p.name, initials: p.initials }))}
          total={card.crew_count}
          leadName={card.lead.name}
        />
        {ghost ? (
          // The flying copy draws the pair's looks only (lane D's shared classes), and "Withdraw" only where
          // RequestedAction draws it: a reply with no request id leaves nothing to withdraw (BLD-F074, BLD-F096)
          card.request ? (
            <div className="tu-req">
              <span className={buttonClass("primary", "full", "crew-join is-inactive")}>
                {REQUESTED_COPY.requested}
              </span>
              {card.request.id ? <span className="link-quiet">{REQUESTED_COPY.withdraw}</span> : null}
            </div>
          ) : null
        ) : card.request ? (
          // DEC-126: "Requested", greyed and inactive but read out, with "Withdraw" under it.
          <RequestedAction
            ideaId={card.id}
            title={card.title}
            request={card.request}
            className="crew-join"
            onWithdrawn={onWithdrawn}
          />
        ) : (
          <Button
            variant="primary"
            size="full"
            className="crew-join"
            icon={<TeamUpIcon />}
            aria-label={CREW_COPY.teamUpOn(card.title, leadFirst(card.lead))}
            onClick={onTeamUp}
            {...teamUpOpener(card.id)}
          >
            {CREW_COPY.teamUp}
          </Button>
        )}
      </div>
    </article>
  );
}

// ---------------------------------------------------------------------------------------------------------------
// The filter panel (L-CREW/5, "Filters open")
// ---------------------------------------------------------------------------------------------------------------
function FilterPanel({
  applied,
  onApply,
  onClose,
}: {
  applied: Filters;
  onApply(filters: Filters, body: CrewDeckResponse): void;
  onClose(): void;
}) {
  const titleId = useId();
  const [draft, setDraft] = useState<Filters>(applied);
  const [view, setView] = useState<CrewDeckResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const box = useRef<HTMLDivElement | null>(null);

  // Live counts: the API counts every option against the other filters as picked here.
  useEffect(() => {
    let live = true;
    getJson<CrewDeckResponse>(crewUrl(draft))
      .then((b) => {
        if (live) {
          setView(b);
          setFailed(false);
        }
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [draft]);

  useEffect(() => {
    box.current?.querySelector<HTMLElement>("button")?.focus({ preventScroll: true });
  }, []);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      onClose();
    }
  };

  const groups: CrewFilterGroup[] = view?.filters ?? [];
  const total = view?.total ?? 0;
  return (
    <div ref={box} className="crew-fpanel" role="dialog" aria-labelledby={titleId} onKeyDown={onKeyDown}>
      <div className="crew-fph">
        <h2 className="crew-fpt" id={titleId}>
          {CREW_COPY.filterTitle}
        </h2>
        <button type="button" className="crew-x" aria-label={CREW_COPY.closeFilters} onClick={onClose}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
            <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
          </svg>
        </button>
      </div>
      <p className="vh" role="status">
        {view ? CREW_COPY.matches(total) : ""}
      </p>
      {failed ? (
        <p className="crew-err" role="alert">
          {CREW_COPY.actionFailed}
        </p>
      ) : null}
      <div className="crew-fgrid">
        {groups.map((g) => (
          <div key={g.key} className={g.key === "looking_for" ? "crew-fg wide" : "crew-fg"}>
            <p className="crew-fgl" aria-hidden="true">
              {g.label}
            </p>
            <MultiChips
              label={g.label}
              options={g.options.map((o) => ({ value: o.value, label: o.label, count: o.count }))}
              values={draft[g.key] ?? []}
              onChange={(values) => setDraft((d) => ({ ...d, [g.key]: values }))}
            />
          </div>
        ))}
      </div>
      <div className="crew-fpf">
        <Button variant="text" onClick={() => setDraft({})}>
          {CREW_COPY.clearAll}
        </Button>
        <Button
          variant="primary"
          disabled={!view}
          onClick={() => {
            if (view) onApply(draft, view);
          }}
        >
          {CREW_COPY.show(total)}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------------------------
// The screen
// ---------------------------------------------------------------------------------------------------------------
type Load = { kind: "loading" } | { kind: "failed" } | { kind: "ready" };

export function CrewScreen(): JSX.Element {
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [data, setData] = useState<CrewDeckResponse | null>(null);
  const [cards, setCards] = useState<CrewCard[]>([]);
  const [at, setAt] = useState(0);
  const [ended, setEnded] = useState(false);
  const [applied, setApplied] = useState<Filters>({});
  const [passedHere, setPassedHere] = useState<string[]>([]);
  const [sent, setSent] = useState<Record<string, TeamUpSent>>({});
  const [added, setAdded] = useState<YourCrew[]>([]);
  /** Requests withdrawn here (DEC-126): their "Your crews" rows from the last read go. */
  const [dropped, setDropped] = useState<string[]>([]);
  /** Requests from the last read withdrawn here, for "You asked to team up on N ideas". */
  const [unasked, setUnasked] = useState(0);
  /** The card asked about, flying to the back of the pile over the slot that was in front (DEC-126). */
  const [flying, setFlying] = useState<{ card: CrewCard; slot: number; n: number } | null>(null);
  const [passed, setPassed] = useState(0);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const filtersBtn = useRef<HTMLButtonElement | null>(null);
  const frontTitle = useRef<HTMLButtonElement | null>(null);
  const endHeading = useRef<HTMLDivElement | null>(null);
  const justSent = useRef<string | null>(null);
  const touch = useRef<{ x: number; y: number } | null>(null);

  const show = useCallback((body: CrewDeckResponse, filters: Filters) => {
    setData(body);
    setCards(body.items);
    setApplied(filters);
    setPassed(body.passed);
    setAt(0);
    setEnded(false);
    setPassedHere([]);
    setAdded([]);
    setSent({});
    setDropped([]);
    setUnasked(0);
    setFlying(null);
    setLoad({ kind: "ready" });
  }, []);

  // Only the latest read may change the screen: a quick run of chip removals, or Clear all then Try again, must
  // not leave an older deck on screen when its answer comes back last.
  const latest = useRef(0);
  const fetchDeck = useCallback(
    (filters: Filters) => {
      const ask = ++latest.current;
      getJson<CrewDeckResponse>(crewUrl(filters))
        .then((b) => {
          if (ask === latest.current) show(b, filtersFrom(b.active));
        })
        .catch(() => {
          if (ask === latest.current) setLoad({ kind: "failed" });
        });
    },
    [show],
  );

  useEffect(() => {
    fetchDeck({});
  }, [fetchDeck]);

  /** After the deck moves, focus goes to what is now in front (or the end of the deck), never into a hidden card. */
  const focusFront = useCallback(() => {
    requestAnimationFrame(() => {
      (frontTitle.current?.isConnected ? frontTitle.current : endHeading.current)?.focus({
        preventScroll: true,
      });
    });
  }, []);

  const asked = Math.max(0, (data?.asked ?? 0) + Object.keys(sent).length - unasked);

  // --- Team up (C-SHEET-TEAMUP) ---------------------------------------------------------------------------------
  const onSent = useCallback(
    (s: TeamUpSent) => {
      justSent.current = s.ideaId;
      setSent((m) => ({ ...m, [s.ideaId]: s }));
      // DEC-126: the card reads "Requested" with "Withdraw" now; it moves to the end of the deck as the sheet closes.
      setCards((cs) =>
        cs.map((c) => (c.id === s.ideaId ? { ...c, request: { id: s.id, kind: s.kind } } : c)),
      );
      const card = cards.find((c) => c.id === s.ideaId);
      if (card) {
        const label = s.after?.line ?? CREW_COPY.waiting(leadFirst(card.lead));
        setAdded((rows) => [
          {
            id: card.id,
            title: card.title,
            status: card.status,
            lead: card.lead,
            state: "waiting",
            label,
            request_id: s.id,
            at: new Date().toISOString(),
          },
          ...rows.filter((r) => r.id !== card.id),
        ]);
      }
    },
    [cards],
  );
  // From the sheet's "Withdraw request" or the card's "Withdraw" (DEC-126 (4)): back to "Team up", and the card stays
  // where it is; "Your crews" drops the row. RequestedAction moves focus to the "Team up" drawn again.
  const onWithdrawn = useCallback(
    (s: TeamUpSent) => {
      justSent.current = null;
      if (sent[s.ideaId]?.id !== s.id) setUnasked((n) => n + 1);
      setSent((m) => {
        const next = { ...m };
        delete next[s.ideaId];
        return next;
      });
      setCards((cs) => cs.map((c) => (c.id === s.ideaId ? { ...c, request: undefined } : c)));
      setAdded((rows) => rows.filter((r) => r.id !== s.ideaId));
      if (s.id) setDropped((d) => [...d, s.id]);
    },
    [sent],
  );
  const onSheetClose = useCallback(() => {
    // "Keep looking" (S-H2.rules/3): after a send, the next card comes to the front. Nothing is passed. DEC-126: the
    // card asked about goes to the end of the deck, where the server keeps it after a reload (L-CREW/3), flying to the
    // back of the pile unless the person asked for less motion. On the last card the deck ends, as before.
    const id = justSent.current;
    justSent.current = null;
    const card = cards[at];
    if (!id || !card || card.id !== id || ended) return;
    if (at >= cards.length - 1) setEnded(true);
    else {
      setCards([...cards.slice(0, at), ...cards.slice(at + 1), card]);
      if (!reducedMotion()) setFlying({ card, slot: at, n: Date.now() });
    }
    focusFront();
  }, [at, cards, ended, focusFront]);

  // The flight is 620 ms; drop the copy if its end never fires (a hidden tab, say). With reduced motion the copy is
  // not drawn (`.crew-fly` is display: none), so its end never fires: drop it at once, also when the person turns
  // reduced motion on while it flies (BLD-F096).
  useEffect(() => {
    if (!flying) return;
    const drop = () => setFlying(null);
    const t = window.setTimeout(drop, reducedMotion() ? 0 : 900);
    const less = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    const onChange = (e: { matches: boolean }) => {
      if (e.matches) drop();
    };
    less?.addEventListener?.("change", onChange);
    return () => {
      window.clearTimeout(t);
      less?.removeEventListener?.("change", onChange);
    };
  }, [flying]);
  const teamUp = useTeamUpSheet({
    onSent,
    onWithdrawn,
    onClose: onSheetClose,
    doneLabel: "Keep looking",
    returnFocus: () => frontTitle.current ?? endHeading.current,
  });

  // --- Passing (L-CREW/6) ---------------------------------------------------------------------------------------
  const pass = useCallback(
    (card: CrewCard) => {
      if (sent[card.id] || passedHere.includes(card.id)) return;
      setPassedHere((p) => [...p, card.id]);
      setPassed((n) => n + 1);
      post<CrewPassResponse>("/api/crew/pass", { idea_id: card.id })
        .then((r) => setPassed(r.passed))
        .catch(() => {
          setPassedHere((p) => p.filter((x) => x !== card.id));
          setPassed((n) => Math.max(0, n - 1));
          setProblem(CREW_COPY.actionFailed);
        });
    },
    [passedHere, sent],
  );

  const onIndexChange = (to: number) => {
    setProblem(null);
    if (to > at) {
      const card = cards[at];
      if (card) pass(card);
    } else if (to < at) {
      const back = cards[to];
      if (back && passedHere[passedHere.length - 1] === back.id) {
        setPassedHere((p) => p.slice(0, -1));
        setPassed((n) => Math.max(0, n - 1));
        post<CrewUndoResponse>("/api/crew/pass/undo")
          .then((r) => setPassed(r.passed))
          .catch(() => setProblem(CREW_COPY.actionFailed));
      }
    }
    setAt(to);
  };

  const onPastEnd = () => {
    setProblem(null);
    const card = cards[at];
    if (card) pass(card);
    setEnded(true);
    focusFront();
  };

  const undoLast = () => {
    setProblem(null);
    post<CrewUndoResponse>("/api/crew/pass/undo")
      .then((r) => {
        setPassed(r.passed);
        if (!r.restored) return;
        const ref = r.restored;
        setPassedHere((p) => p.filter((x) => x !== ref));
        const j = cards.findIndex((c) => c.id === ref);
        const card = j >= 0 ? cards[j] : r.card;
        if (!card) return;
        // The card passed last comes back on top of the pile.
        const rest = cards.filter((c) => c.id !== ref);
        const pos = ended ? rest.length : j >= 0 && j < at ? at - 1 : at;
        rest.splice(pos, 0, card);
        setCards(rest);
        setAt(pos);
        setEnded(false);
        focusFront();
      })
      .catch(() => setProblem(CREW_COPY.actionFailed));
  };

  const seeAgain = () => {
    setProblem(null);
    post<CrewResetResponse>("/api/crew/pass/reset")
      .then(() => fetchDeck(applied))
      .catch(() => setProblem(CREW_COPY.actionFailed));
  };

  const removeFilter = (key: CrewFilterKey, value: string) => {
    const next: Filters = { ...applied, [key]: (applied[key] ?? []).filter((v) => v !== value) };
    fetchDeck(next);
  };

  // Phone: swipe left for the next card, swipe up for the detail (S-H2.phone).
  const onTouchStart = (e: TouchEvent<HTMLDivElement>) => {
    const t = e.touches[0];
    touch.current = t ? { x: t.clientX, y: t.clientY } : null;
  };
  const onTouchEnd = (e: TouchEvent<HTMLDivElement>) => {
    const start = touch.current;
    const t = e.changedTouches[0];
    touch.current = null;
    if (!start || !t || ended) return;
    const dx = t.clientX - start.x;
    const dy = t.clientY - start.y;
    if (dx < -60 && Math.abs(dy) < 40) {
      if (at >= cards.length - 1) onPastEnd();
      else onIndexChange(at + 1);
    } else if (dy < -60 && Math.abs(dx) < 40 && cards[at]) {
      setPreview(cards[at].id);
    }
  };

  // --- Rendering --------------------------------------------------------------------------------------------------
  const crews = [
    ...added,
    ...(data?.your_crews?.items ?? []).filter(
      (r) => !added.some((a) => a.id === r.id) && !(r.request_id && dropped.includes(r.request_id)),
    ),
  ];
  const inUse = filterCount(applied);

  let centre: JSX.Element;
  if (load.kind === "loading") {
    centre = (
      <div className="crew-card crew-skel" aria-busy="true">
        <p className="vh" role="status">
          {CREW_COPY.loading}
        </p>
      </div>
    );
  } else if (load.kind === "failed" || !data) {
    centre = (
      <div className="crew-end" role="alert">
        <Empty
          title={CREW_COPY.failedTitle}
          align="center"
          level={2}
          action={
            <Button variant="line" onClick={() => fetchDeck(applied)}>
              {CREW_COPY.retry}
            </Button>
          }
        >
          {CREW_COPY.failedBody}
        </Empty>
      </div>
    );
  } else if (data.state === "nothing_yet") {
    centre = (
      <div className="crew-end" role="status" ref={endHeading} tabIndex={-1}>
        <span className="crew-end-ic" aria-hidden="true">
          +
        </span>
        <Empty
          title={CREW_COPY.nothingTitle}
          align="center"
          level={2}
          action={
            <ButtonLink variant="line" href="/wall">
              {CREW_COPY.browseWall}
            </ButtonLink>
          }
        >
          {CREW_COPY.nothingBody}
        </Empty>
      </div>
    );
  } else if (ended || data.state === "everyone_seen" || (cards.length === 0 && inUse === 0)) {
    centre = (
      <div className="crew-end" role="status" ref={endHeading} tabIndex={-1}>
        <Empty
          title={CREW_COPY.endTitle}
          align="center"
          level={2}
          action={
            passed > 0 ? (
              <Button variant="line" onClick={seeAgain}>
                {CREW_COPY.seeAgain}
              </Button>
            ) : undefined
          }
        >
          {CREW_COPY.endBody(asked)}
        </Empty>
      </div>
    );
  } else if (cards.length === 0) {
    centre = (
      <div className="crew-end" role="status" ref={endHeading} tabIndex={-1}>
        <Empty
          title={CREW_COPY.noneMatchTitle}
          align="center"
          level={2}
          action={
            <Button variant="line" onClick={() => fetchDeck({})}>
              {CREW_COPY.clearAll}
            </Button>
          }
        >
          {CREW_COPY.noneMatchBody}
        </Empty>
      </div>
    );
  } else {
    centre = (
      <div className="crew-deck" onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
        <Deck
          label={CREW_COPY.deckLabel}
          cards={cards.map((c, i) => (
            <div key={c.id} className="crew-slot">
              <CardView
                key="card"
                card={c}
                front={i === at}
                onPreview={() => setPreview(c.id)}
                onTeamUp={() => teamUp.open(c.id)}
                onWithdrawn={onWithdrawn}
                titleRef={(el) => {
                  frontTitle.current = el;
                }}
              />
              {flying && flying.slot === i ? (
                <div
                  key={flying.n}
                  className="crew-fly"
                  aria-hidden="true"
                  inert
                  onAnimationEnd={(e) => {
                    if (e.target === e.currentTarget) setFlying(null);
                  }}
                >
                  <CardView
                    card={flying.card}
                    front={false}
                    ghost
                    onPreview={noop}
                    onTeamUp={noop}
                    onWithdrawn={noop}
                  />
                </div>
              ) : null}
            </div>
          ))}
          index={at}
          onIndexChange={onIndexChange}
          onPastEnd={onPastEnd}
        />
      </div>
    );
  }

  const previewCard = preview ? cards.find((c) => c.id === preview) : undefined;
  const previewSent = preview ? sent[preview] : undefined;

  return (
    <div className="crew-page arrive">
      <PhoneBar back={{ href: "/", label: CREW_COPY.home }} title={CREW_COPY.title} />
      <div className="crew-left">
        <p className="crew-back-row">
          <Link className="crew-back" href="/">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
              <path d="m15 5-7 7 7 7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
            </svg>
            {CREW_COPY.home}
          </Link>
        </p>
        <h1 className="crew-h1">{CREW_COPY.title}</h1>
        <p className="crew-lead">{CREW_COPY.lead}</p>
        {data && data.state !== "nothing_yet" ? (
          <div className="crew-fanchor">
            <div className="crew-fbar">
              <button
                ref={filtersBtn}
                type="button"
                className="crew-fbtn"
                aria-expanded={filtersOpen}
                aria-haspopup="dialog"
                onClick={() => setFiltersOpen((o) => !o)}
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  aria-hidden="true"
                  focusable="false"
                >
                  <path d="M4 7h10M18 7h2M4 17h4M12 17h8" />
                  <circle cx="16" cy="7" r="2" />
                  <circle cx="10" cy="17" r="2" />
                </svg>
                {CREW_COPY.filters}
                {inUse > 0 ? <span className="crew-fcount">{inUse}</span> : null}
              </button>
              <p className="crew-fres">{CREW_COPY.count(data.total)}</p>
            </div>
            {filtersOpen ? (
              <FilterPanel
                applied={applied}
                onClose={() => {
                  setFiltersOpen(false);
                  filtersBtn.current?.focus({ preventScroll: true });
                }}
                onApply={(_draft, body) => {
                  setFiltersOpen(false);
                  show(body, filtersFrom(body.active));
                  filtersBtn.current?.focus({ preventScroll: true });
                }}
              />
            ) : null}
            {data.active.length ? (
              <div className="crew-fact">
                {data.active.map((a) => (
                  <button
                    key={`${a.key}:${a.value}`}
                    type="button"
                    className="crew-fpill"
                    aria-label={CREW_COPY.removeFilter(a.label)}
                    onClick={() => removeFilter(a.key, a.value)}
                  >
                    {a.label}
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      aria-hidden="true"
                      focusable="false"
                    >
                      <path
                        d="M6 6l12 12M18 6 6 18"
                        stroke="currentColor"
                        strokeWidth="2.4"
                        strokeLinecap="round"
                      />
                    </svg>
                  </button>
                ))}
                <Button variant="text" className="crew-fclr" onClick={() => fetchDeck({})}>
                  {CREW_COPY.clearAll}
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="crew-centre">
        {centre}
        {problem ? (
          <p className="crew-err" role="alert">
            {problem}
          </p>
        ) : null}
      </div>

      <aside className="crew-side" aria-labelledby="crew-side-t">
        <h2 className="crew-side-t" id="crew-side-t">
          {CREW_COPY.crews}
        </h2>
        {crews.length ? (
          <ul className="crew-rows">
            {crews.map((r) => (
              <li key={r.id} className="crew-row">
                {/* The title is the link (the whole row takes the click). Its name carries the state, as the board
                    names it, and starts with the visible title (WCAG 2.5.3); a hidden suffix would gain a space in
                    browsers' names, so it is a label. */}
                <Link
                  className="crew-row-t"
                  href={`/ideas/${encodeURIComponent(r.id)}`}
                  aria-label={CREW_COPY.crewRow(r.title, r)}
                >
                  {r.title}
                </Link>
                <span className="crew-row-m">{CREW_COPY.leadLine(r.lead.name, r.lead.area)}</span>
                <span className={r.state === "waiting" ? "crew-row-s" : "crew-row-s ok"}>
                  {r.state === "waiting" ? r.label : CREW_COPY.onCrew}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="crew-side-e">{CREW_COPY.crewsEmpty}</p>
        )}
        <div className="crew-side-p">
          <span>{passed > 0 ? CREW_COPY.passed(passed) : CREW_COPY.nonePassed}</span>
          {passed > 0 ? (
            <Button variant="text-blue" onClick={undoLast}>
              {CREW_COPY.undo}
            </Button>
          ) : null}
        </div>
        <Link className="crew-all" href={data?.your_crews?.teamed_link ?? "/my-ideas?list=teamed"}>
          {CREW_COPY.allCrews}
        </Link>
      </aside>

      {previewCard ? (
        <IdeaPreviewDialog
          ideaId={previewCard.id}
          view="sharer"
          open
          yours="idea"
          preview={previewCard}
          matchReason={previewCard.reason}
          onClose={() => setPreview(null)}
          onPrimary={teamUp.open}
          primaryDone={
            previewSent
              ? (previewSent.after?.line ?? CREW_COPY.waiting(leadFirst(previewCard.lead)))
              : previewCard.request
                ? CREW_COPY.waiting(leadFirst(previewCard.lead))
                : undefined
          }
        />
      ) : null}
      {teamUp.sheet}
    </div>
  );
}
