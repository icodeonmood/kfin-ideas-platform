"use client";

/**
 * C-SHEET-TEAMUP: the one team-up request sheet (L-TEAMUP; L-MERGE.request on Check it), BLD-F070 to BLD-F073.
 *
 * Opened from "Team up" on Find your crew (S-H2), the similar ideas on Check it (S-05, through C-PREVIEW's
 * `onPrimary` or a tile), Status (S-06) and the idea's page (S-09). Two steps, changed in place:
 * - compose: the note to the lead, pre-filled (GET /api/ideas/:id/team-up/draft-note), and the ideas brought along
 *   (C-DROPDOWN), or on Check it the draft's single choice, "Ask {lead} to merge mine in" or "Keep mine separate";
 * - sent: "Sent to {lead}", the note shown back, "Withdraw request" and one button to carry on.
 * Opened on an idea the person already asked about (GET /api/ideas/:id/team-up), it opens on the sent step.
 *
 * Behaviour (C-SHEET-TEAMUP.a11y, F-MOTION.focus): mounted at the page root through a portal; role="dialog",
 * aria-modal, labelled by the title and described by the line under it. Focus starts in the note with the cursor at
 * the end, is trapped inside, and returns to the opener on close. Escape, the cross and the backdrop close without
 * sending; what was typed is kept for this session if the sheet is reopened.
 *
 * Privacy (non-negotiables 3, 4 and 7): the note goes only to the API, which masks it before anyone else reads it;
 * the sent step shows back what the API returns. Nothing is logged. The lead is named only as the API names them: a
 * lead who hid their name from the Wall, or has left, comes as lane C's hidden person ("A colleague", no initials)
 * and every line says "the lead" (BLD-F029, DEC-104).
 */
import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type JSX,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Dropdown } from "@/components/ui/dropdown";
import { Field, FieldMsg } from "@/components/ui/field";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import {
  IDEMPOTENCY_HEADER,
  type DraftMergeRequestState,
  type TeamUpAfter,
  type TeamUpDraftNote,
  type TeamUpMine,
  type TeamUpSendResponse,
} from "@/lib/contracts/api";
import type { PersonRef } from "@/lib/contracts/entities";
import { sparkBurst } from "@/lib/motion/spark";

import "./teamup-sheet.css";

// ---------------------------------------------------------------------------------------------------------------
// Words (C-SHEET-TEAMUP, Crew.md view=Request and view=Request sent). No gendered pronoun for a real person
// (BLD-E008): the lead is named by first name, or is "the lead" when the API does not name them (BLD-F029; `lead`
// below is `leadWord(…)`). Lines the pack does not draw are listed in docs/hr-wording/lane-f.md §4.
// ---------------------------------------------------------------------------------------------------------------
/** How the sheet says a lead the API does not name (they hid their name from the Wall, or have left). */
export const THE_LEAD = "the lead";
/** Lane C's name for a hidden person (`similar.preview.HIDDEN_NAME`). */
const HIDDEN_NAME = "A colleague";

/**
 * The lead in a sentence: their first name, or "the lead" when the API sends lane C's hidden person (no initials,
 * "A colleague"), as the crew cards do (BLD-F042, BLD-F029). Empty while nothing has loaded.
 */
export function leadWord(
  lead: Pick<PersonRef, "name" | "first_name" | "initials"> | null | undefined,
): string {
  if (!lead) return "";
  if (!lead.initials || lead.name === HIDDEN_NAME || lead.first_name === HIDDEN_NAME) return THE_LEAD;
  return lead.first_name || lead.name;
}

/** "the lead" starts a sentence as "The lead"; a name is left as it is. */
const cap = (lead: string) => (lead === THE_LEAD ? "The lead" : lead);

export const TEAMUP_COPY = {
  title: (lead: string) => `Team up with ${lead}`,
  line: (lead: string, title: string) =>
    lead === THE_LEAD
      ? `The lead of “${title}” decides who joins. Tell them what you bring.`
      : `${lead} leads “${title}” and decides who joins. Tell ${lead} what you bring.`,
  close: "Close without sending",
  noteLabel: (lead: string) => `Your note to ${lead}`,
  hintDrafted: "We drafted this from your idea. Change anything you like.",
  hintShort: (min: number) => `Add a little more: at least ${min} characters.`,
  hintGood: "Looks good.",
  /** NOT DRAWN (V-FIELDS.teamup/1 has a 600 limit): the API's own line for `note_too_long`. */
  hintLong: (max: number) => `Keep your note to ${max} characters.`,
  bring: "Bring your ideas along",
  /** NOT DRAWN: the open list when the person has no shared idea to bring. */
  bringNone: "You have no shared ideas to bring yet.",
  /** NOT DRAWN: the name of the Check it choice (a radio group needs one). */
  draftChoice: "Your draft",
  merge: (lead: string) => `Ask ${lead} to merge mine in`,
  mergeHelp: (lead: string) =>
    `${cap(lead)} decides. If ${lead} accepts, yours joins that idea with credit to you. If not, you send yours on its own.`,
  separate: "Keep mine separate",
  separateHelp: "Team up, and send yours as its own idea",
  privacy: (lead: string, brought: number) =>
    brought === 0
      ? `${cap(lead)} sees your name, your note.`
      : `${cap(lead)} sees your name, your note and the ${brought === 1 ? "idea" : "ideas"} you bring.`,
  send: (lead: string) => `Send to ${lead}`,
  sending: "Sending…",
  sentTitle: (lead: string) => `Sent to ${lead}`,
  sentLine: (lead: string) =>
    `${cap(lead)} reads your note, then approves or declines. You’ll hear in your Inbox.`,
  yourNote: "Your note",
  bringing: (titles: string[]) => `Bringing ${quotedList(titles)}`,
  withdraw: "Withdraw request",
  withdrawing: "Withdrawing…",
  done: "Done",
  keepLooking: "Keep looking",
  /** NOT DRAWN: the loading line, read by a screen reader only. */
  loading: "Loading your note",
  /** NOT DRAWN: the sheet's title when it could not load. */
  failedTitle: "Team up",
  retry: "Try again",
  /** The opener's state when the person cannot ask (the API's own lines for these codes). */
  youLead: "You lead this idea.",
  waiting: (lead: string) => `Waiting for ${lead}`,
  onCrew: "You’re on the crew.",
  closed: "This idea is no longer open to team up.",
  /** Errors with no ready-made message from the API (docs/hr-wording/lane-f.md). */
  notFound: "We couldn’t find that.",
  signIn: "Sign in again to team up.",
  offline: "Check your connection, then try again.",
  failed: "Something went wrong. Please try again.",
} as const;

/** “A”, “A” and “B”, “A”, “B” and “C”. */
export function quotedList(titles: string[]): string {
  const q = titles.map((t) => `“${t}”`);
  return q.length <= 1 ? (q[0] ?? "") : `${q.slice(0, -1).join(", ")} and ${q[q.length - 1]}`;
}

/** The hint under the note (C-SHEET-TEAMUP.compose/3), and whether the note can be sent. */
export function noteHint(
  note: string,
  drafted: string,
  min: number,
  max: number,
): { kind: "drafted" | "good" | "short" | "long"; text: string; ok: boolean } {
  const n = note.trim().length;
  if (n < min) return { kind: "short", text: TEAMUP_COPY.hintShort(min), ok: false };
  if (n > max) return { kind: "long", text: TEAMUP_COPY.hintLong(max), ok: false };
  if (note === drafted) return { kind: "drafted", text: TEAMUP_COPY.hintDrafted, ok: true };
  return { kind: "good", text: TEAMUP_COPY.hintGood, ok: true };
}

export type SheetError = { code: string; message: string; field?: string };

/**
 * Every error the sheet can meet, with its ready-made message: the worker's `{error: {code, message, field?}}`
 * (A-API.conventions/2), the proxy's `{error, banner}` (kill switches, §7.6) and the bare codes the proxy and the
 * session check answer with.
 */
export function errorFrom(status: number, body: unknown): SheetError {
  const raw = body && typeof body === "object" ? (body as Record<string, unknown>) : {};
  const e = raw.error;
  if (e && typeof e === "object") {
    const { code, message, field } = e as Record<string, unknown>;
    const c = typeof code === "string" ? code : "error";
    if (typeof message === "string" && message) {
      return typeof field === "string" ? { code: c, message, field } : { code: c, message };
    }
    if (c === "not_found") return { code: c, message: TEAMUP_COPY.notFound };
    return { code: c, message: TEAMUP_COPY.failed };
  }
  const code = typeof e === "string" ? e : status === 404 ? "not_found" : "error";
  if (typeof raw.banner === "string" && raw.banner) return { code, message: raw.banner };
  if (code === "sign_in_required" || code === "forbidden" || code === "privacy_notice_required")
    return { code, message: TEAMUP_COPY.signIn };
  if (status === 401 || status === 403) return { code, message: TEAMUP_COPY.signIn };
  if (code === "not_found") return { code, message: TEAMUP_COPY.notFound };
  return { code, message: TEAMUP_COPY.failed };
}

// ---------------------------------------------------------------------------------------------------------------
// The API (A-API.team-up, A-API.drafts merge-request; BLD-F010, BLD-F015, BLD-F020)
// ---------------------------------------------------------------------------------------------------------------
const enc = encodeURIComponent;
export const teamupUrls = {
  mine: (ideaId: string) => `/api/ideas/${enc(ideaId)}/team-up`,
  draftNote: (ideaId: string) => `/api/ideas/${enc(ideaId)}/team-up/draft-note`,
  send: (ideaId: string) => `/api/ideas/${enc(ideaId)}/team-up`,
  mergeRequest: (draftId: string) => `/api/drafts/${enc(draftId)}/merge-request`,
  request: (requestId: string) => `/api/team-up/${enc(requestId)}`,
  me: "/api/me",
} as const;

type Reply = { ok: true; body: unknown } | { ok: false; error: SheetError };

async function call(url: string, init: RequestInit = {}): Promise<Reply> {
  let res: Response;
  try {
    res = await fetch(url, {
      credentials: "same-origin",
      ...init,
      headers: { accept: "application/json", ...(init.headers as Record<string, string> | undefined) },
    });
  } catch {
    // IDs only, and nothing logged: the sheet shows its own line (non-negotiable 3).
    return { ok: false, error: { code: "offline", message: TEAMUP_COPY.offline } };
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  return res.ok ? { ok: true, body } : { ok: false, error: errorFrom(res.status, body) };
}

/**
 * What the sent step shows and what the opener is told, by `onSent` after a send and by `onWithdrawn` after a withdraw
 * (from the sheet's "Withdraw request" or a card's "Withdraw", `RequestedAction`).
 *
 * DEC-126 (BLD-F094): a host card needs nothing else to draw "Requested" with "Withdraw" in place of "Team up":
 * `{ id, kind }` is the card's request (`CrewCard.request`), so after `onSent` set
 * `card.request = { id: sent.id, kind: sent.kind }` and draw `<RequestedAction ideaId={sent.ideaId} request=… />`;
 * after `onWithdrawn` drop `card.request` and draw "Team up" again, in the same place.
 */
export interface TeamUpSent {
  /** "teamup" for a team-up request, "merge" for a draft's merge request (BLD-F010). */
  kind: "teamup" | "merge";
  /**
   * The request id: `DELETE /api/team-up/:id` withdraws either kind. Empty only when a send's reply carried none;
   * then there is nothing to withdraw (BLD-F074).
   */
  id: string;
  /** The idea asked about, its reference (IDEA-2026-001412): the card to change. */
  ideaId: string;
  /** The note as the API keeps it (masked). Empty after a withdraw from a card, which never reads the note. */
  note: string;
  /** Titles of what was brought along. Empty after a withdraw from a card. */
  brought: string[];
  /**
   * What the opener shows now (C-SHEET-TEAMUP.after; L-MERGE.request/4 on Check it): after a send `line` is
   * "Waiting for Ravi" (or "Waiting for the lead"), the words "Your crews" keeps (DEC-126 (5)); after a withdraw it
   * is the API's state for "Team up" again, or null.
   */
  after: TeamUpAfter | null;
}

function fromRequest(
  ideaId: string,
  r: (TeamUpSendResponse | NonNullable<TeamUpMine["request"]>) & { after?: TeamUpAfter | null },
  after: TeamUpAfter | null,
): TeamUpSent {
  return {
    kind: r.request === "merge" ? "merge" : "teamup",
    id: r.id,
    ideaId,
    note: r.note ?? "",
    brought: (r.brought ?? []).map((b) => b.title).filter(Boolean),
    after,
  };
}

function isMine(x: unknown): x is TeamUpMine {
  return !!x && typeof x === "object" && "lead" in x && "why_not" in x;
}

function isDraftNote(x: unknown): x is TeamUpDraftNote & Required<Pick<TeamUpDraftNote, "idea" | "lead">> {
  if (!x || typeof x !== "object") return false;
  const d = x as Partial<TeamUpDraftNote>;
  return typeof d.note === "string" && Array.isArray(d.own_ideas) && !!d.idea && !!d.lead;
}

function isRequest(x: unknown): x is TeamUpSendResponse {
  return !!x && typeof x === "object" && typeof (x as { id?: unknown }).id === "string";
}

/**
 * `DELETE /api/team-up/:id` (L-TEAMUP.rules/3, L-MERGE.request/8): withdraws a waiting team-up request or a draft's
 * merge request. The sheet's "Withdraw request" and a card's "Withdraw" (`RequestedAction`, DEC-126) both call it.
 */
export async function withdrawRequest(
  requestId: string,
): Promise<{ ok: true; after: TeamUpAfter | null } | { ok: false; error: SheetError }> {
  const r = await call(teamupUrls.request(requestId), { method: "DELETE" });
  if (!r.ok) return r;
  return { ok: true, after: isRequest(r.body) ? (r.body.after ?? null) : null };
}

/** "Kavya Iyer" → "KI": the person's own disc, when the opener does not pass it. */
function initialsOf(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const first = words[0]?.[0] ?? "";
  const last = words.length > 1 ? (words[words.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase();
}

type Who = { key: string; initials: string };
/** The signed-in person (GET /api/me), asked on every open: their initials for the avatar pair, and the key that
 * keeps one person's typed note from showing to the next person who signs in on the same page (BLD-F074). */
async function whoAmI(): Promise<Who | null> {
  const r = await call(teamupUrls.me);
  const b = r.ok && r.body && typeof r.body === "object" ? (r.body as Record<string, unknown>) : null;
  const name = typeof b?.name === "string" ? b.name : "";
  const key = [b?.contributor_code, b?.email].find((v): v is string => typeof v === "string" && v !== "");
  return key ? { key, initials: initialsOf(name) } : null;
}

// ---------------------------------------------------------------------------------------------------------------
// What was typed, kept for this session (C-SHEET-TEAMUP.a11y): cleared when the request is sent, and all of it when
// another person is signed in (BLD-F074). Nothing is kept while the sheet does not know who is signed in.
// ---------------------------------------------------------------------------------------------------------------
type Kept = { note: string; picks: string[]; choice: Choice };
type Choice = "separate" | "merge";
const kept = new Map<string, Kept>();
let keptFor: string | null = null;
const keyOf = (ideaId: string, draftId?: string) => `${ideaId}|${draftId ?? ""}`;

/** The text kept for this person, after forgetting anyone else's. */
function keptBy(who: string | null): Map<string, Kept> | null {
  if (!who) return null;
  if (keptFor !== who) {
    kept.clear();
    keptFor = who;
  }
  return kept;
}

// ---------------------------------------------------------------------------------------------------------------
// The component
// ---------------------------------------------------------------------------------------------------------------
export interface TeamUpSheetProps {
  /** The idea asked about (its reference, IDEA-2026-001412). */
  ideaId: string;
  open: boolean;
  /** Escape, the cross, the backdrop, "Done" or "Keep looking", and after a withdraw. Focus returns to the opener. */
  onClose(): void;
  /**
   * After a send: the request (`id`, `kind`) and what the opener shows now. On a crew card that is "Requested" with
   * "Withdraw" (DEC-126, `RequestedAction`); elsewhere "Waiting for Ravi" with Withdraw.
   */
  onSent?(sent: TeamUpSent): void;
  /** After "Withdraw request" on the sent step: the opener goes back to "Team up" (C-SHEET-TEAMUP.after). */
  onWithdrawn?(sent: TeamUpSent): void;
  /** Check it only: the person's unsent draft. The ideas dropdown becomes the merge choice (L-MERGE.request/1). */
  draftId?: string;
  /** Check it only: the draft's title, for "Bringing “…”" once a merge request is sent. */
  draftTitle?: string;
  /** The button that carries on after sending: "Keep looking" on Find your crew, "Done" elsewhere. */
  doneLabel?: "Done" | "Keep looking";
  /** The signed-in person's initials, when the host has them; otherwise from GET /api/me. */
  me?: { initials: string };
  /**
   * Where focus goes on close when the button that opened the sheet is gone (the host re-drew it as "Waiting for
   * Ravi"). Without it, the sheet looks for an element marked `{...teamUpOpener(ideaId)}` (WCAG 2.4.3, BLD-F074).
   */
  returnFocus?(): HTMLElement | null | undefined;
}

/**
 * Spread on whatever stands where "Team up" is for this idea: the "Team up" button itself, and "Requested" once the
 * person has asked (DEC-126, `RequestedAction` marks it). Focus returns to it when the sheet closes, and moves to the
 * "Team up" drawn again after a card's "Withdraw" (WCAG 2.4.3).
 */
export function teamUpOpener(ideaId: string): { "data-teamup-opener": string } {
  return { "data-teamup-opener": ideaId };
}

/** The element marked `teamUpOpener(ideaId)` on the page now, if any. */
export function markedOpener(ideaId: string): HTMLElement | null {
  for (const el of Array.from(document.querySelectorAll<HTMLElement>("[data-teamup-opener]"))) {
    if (el.dataset.teamupOpener === ideaId && el.isConnected) return el;
  }
  return null;
}

const noSubscribe = () => () => {};

export function TeamUpSheet(props: TeamUpSheetProps): JSX.Element | null {
  // Portals need the page: render nothing on the server and in the first hydration pass.
  const onClient = useSyncExternalStore(
    noSubscribe,
    () => true,
    () => false,
  );
  if (!props.open || !onClient) return null;
  // Keyed so another idea or draft starts from a clean load.
  return createPortal(<Sheet key={keyOf(props.ideaId, props.draftId)} {...props} />, document.body);
}

type Loaded = {
  /** The signed-in person's key for what they typed; null when GET /api/me did not answer. */
  who: string | null;
  lead: PersonRef;
  title: string;
  drafted: string;
  own: { id: string; title: string; meta?: string }[];
  min: number;
  max: number;
};
type View =
  | { kind: "loading" }
  | { kind: "failed"; error: SheetError; lead?: PersonRef }
  | { kind: "cannot"; lead: PersonRef; message: string }
  | { kind: "compose"; data: Loaded }
  | { kind: "sent"; lead: PersonRef; sent: TeamUpSent };

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function Sheet(props: TeamUpSheetProps) {
  const { ideaId, onClose } = props;
  const boxRef = useRef<HTMLElement>(null);
  const titleId = useId();
  const lineId = useId();
  const [attempt, setAttempt] = useState(0);
  const [view, setView] = useState<View>({ kind: "loading" });
  const [initials, setInitials] = useState<string | null>(props.me?.initials ?? null);

  // Load my state and the pre-filled note together (BLD-F015, BLD-F011).
  useEffect(() => {
    let live = true;
    Promise.all([call(teamupUrls.mine(ideaId)), call(teamupUrls.draftNote(ideaId)), whoAmI()]).then(
      ([mine, note, who]) => {
        if (!live) return;
        if (who && !props.me) setInitials(who.initials);
        const m = mine.ok && isMine(mine.body) ? mine.body : null;
        if (m?.request && m.request.state === "sent") {
          setView({ kind: "sent", lead: m.lead, sent: fromRequest(ideaId, m.request, m.after) });
          return;
        }
        if (m?.why_not) {
          // A request still waiting that did not come back as one: say so rather than offer a send the API refuses.
          const first = leadWord(m.lead);
          const message =
            m.why_not === "idea_closed"
              ? TEAMUP_COPY.closed
              : m.why_not === "already_requested"
                ? (m.after?.line ?? TEAMUP_COPY.waiting(first))
                : m.me === "lead"
                  ? TEAMUP_COPY.youLead
                  : TEAMUP_COPY.onCrew;
          setView({ kind: "cannot", lead: m.lead, message });
          return;
        }
        if (!note.ok || !isDraftNote(note.body)) {
          const error = !note.ok
            ? note.error
            : !mine.ok
              ? mine.error
              : { code: "error", message: TEAMUP_COPY.failed };
          setView({ kind: "failed", error, lead: m?.lead });
          return;
        }
        const d = note.body;
        setView({
          kind: "compose",
          data: {
            who: who?.key ?? null,
            lead: d.lead,
            title: d.idea.title,
            drafted: d.note,
            own: d.own_ideas.map((o) => ({ id: o.id, title: o.title, meta: o.meta })),
            min: d.min_chars ?? 30,
            max: d.max_chars ?? 600,
          },
        });
      },
    );
    return () => {
      live = false;
    };
    // `props.me` is read once, when the sheet loads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ideaId, attempt]);

  const returnFocus = useRef(props.returnFocus);
  useEffect(() => {
    returnFocus.current = props.returnFocus;
  });

  // Focus in on open, trapped while open, back to the opener on close (F-MOTION.focus/1, /2).
  useLayoutEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const box = boxRef.current;
    box?.focus({ preventScroll: true });
    const keepInside = (e: FocusEvent) => {
      if (box && e.target instanceof Node && !box.contains(e.target)) box.focus({ preventScroll: true });
    };
    document.addEventListener("focusin", keepInside);
    const root = document.documentElement;
    const overflow = root.style.overflow;
    root.style.overflow = "hidden";
    // Back to the opener; if the host has re-drawn it ("Team up" is now "Waiting for Ravi"), to what the host names
    // or marks in its place, once the host's new markup is on the page (WCAG 2.4.3, BLD-F074).
    const back = (): HTMLElement | null => {
      if (opener && opener.isConnected) return opener;
      const given = returnFocus.current?.();
      if (given && given.isConnected) return given;
      return markedOpener(ideaId);
    };
    return () => {
      document.removeEventListener("focusin", keepInside);
      root.style.overflow = overflow;
      const now = back();
      if (now) now.focus({ preventScroll: true });
      else queueMicrotask(() => back()?.focus({ preventScroll: true }));
    };
  }, [ideaId]);

  const close = useCallback(() => onClose(), [onClose]);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      close();
      return;
    }
    if (e.key !== "Tab") return;
    const box = boxRef.current;
    if (!box) return;
    const items = Array.from(box.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (el) => !el.closest("[hidden]"),
    );
    const first = items[0];
    const last = items[items.length - 1];
    if (!first || !last) {
      e.preventDefault();
      box.focus();
      return;
    }
    const active = document.activeElement;
    if (e.shiftKey && (active === first || active === box)) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && (active === last || !box.contains(active))) {
      e.preventDefault();
      first.focus();
    }
  };

  const lead = view.kind === "loading" ? undefined : view.kind === "compose" ? view.data.lead : view.lead;
  const first = leadWord(lead);

  return (
    <div className="tus-wrap" onKeyDown={onKeyDown}>
      <div className="tus-back" aria-hidden="true" onClick={close} />
      <section
        ref={boxRef}
        className={view.kind === "sent" ? "tus sent" : "tus"}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={view.kind === "loading" ? undefined : lineId}
        aria-busy={view.kind === "loading" ? true : undefined}
        tabIndex={-1}
      >
        <div className="tus-top">
          <span className="tus-pair" aria-hidden="true">
            {view.kind === "sent" ? null : (
              <>
                <Avatar initials={initials ?? ""} size={44} ring="neutral" />
                {lead ? <Avatar initials={lead.initials} size={44} ring="neutral" /> : null}
              </>
            )}
          </span>
          <button type="button" className="tus-x" aria-label={TEAMUP_COPY.close} onClick={close}>
            <CloseIcon />
          </button>
        </div>
        {view.kind === "loading" ? (
          <LoadingBody titleId={titleId} />
        ) : view.kind === "failed" ? (
          <Note
            titleId={titleId}
            lineId={lineId}
            title={view.lead ? TEAMUP_COPY.title(first) : TEAMUP_COPY.failedTitle}
            message={<FieldMsg id={lineId}>{view.error.message}</FieldMsg>}
            action={
              <Button
                variant="primary"
                onClick={() => {
                  boxRef.current?.focus({ preventScroll: true }); // the button goes with the step
                  setView({ kind: "loading" });
                  setAttempt((n) => n + 1);
                }}
              >
                {TEAMUP_COPY.retry}
              </Button>
            }
          />
        ) : view.kind === "cannot" ? (
          <Note
            titleId={titleId}
            lineId={lineId}
            title={TEAMUP_COPY.title(first)}
            message={
              <p id={lineId} className="tus-p">
                {view.message}
              </p>
            }
            action={
              <Button variant="primary" onClick={close}>
                {props.doneLabel ?? TEAMUP_COPY.done}
              </Button>
            }
          />
        ) : view.kind === "compose" ? (
          <Compose
            {...props}
            data={view.data}
            first={first}
            titleId={titleId}
            lineId={lineId}
            onSentHere={(sent) => {
              setView({ kind: "sent", lead: view.data.lead, sent });
              props.onSent?.(sent);
            }}
          />
        ) : (
          <SentBody
            {...props}
            sent={view.sent}
            first={first}
            titleId={titleId}
            lineId={lineId}
            onWithdrawnHere={(sent) => {
              props.onWithdrawn?.(sent);
              close();
            }}
          />
        )}
      </section>
    </div>
  );
}

function LoadingBody({ titleId }: { titleId: string }) {
  return (
    <Loading what={TEAMUP_COPY.loading}>
      <h2 id={titleId} className="tus-h">
        <span className="vh">{TEAMUP_COPY.loading}</span>
        <Skeleton width="62%" height={26} />
      </h2>
      <div className="tus-sk">
        <Skeleton width="92%" />
        <Skeleton width="70%" />
        <Skeleton width="100%" height={112} style={{ marginTop: 18 }} />
      </div>
    </Loading>
  );
}

/** A sheet with one thing to say: it could not load, or the person cannot ask (on the crew, the idea closed). */
function Note({
  titleId,
  title,
  message,
  action,
}: {
  titleId: string;
  lineId: string;
  title: string;
  message: ReactNode;
  action: ReactNode;
}) {
  return (
    <>
      <h2 id={titleId} className="tus-h">
        {title}
      </h2>
      {message}
      <div className="tus-f">{action}</div>
    </>
  );
}

// ---------------------------------------------------------------------------------------------------------------
// Step 1: write the request (C-SHEET-TEAMUP.compose)
// ---------------------------------------------------------------------------------------------------------------
function Compose({
  ideaId,
  draftId,
  draftTitle,
  data,
  first,
  titleId,
  lineId,
  onSentHere,
}: TeamUpSheetProps & {
  data: Loaded;
  first: string;
  titleId: string;
  lineId: string;
  onSentHere(sent: TeamUpSent): void;
}) {
  const key = keyOf(ideaId, draftId);
  const store = keptBy(data.who);
  const before = store?.get(key);
  const [note, setNote] = useState(before?.note ?? data.drafted);
  const [picks, setPicks] = useState<string[]>(before?.picks ?? []);
  const [choice, setChoice] = useState<Choice>(before?.choice ?? "separate");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<SheetError | null>(null);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const sendRef = useRef<HTMLButtonElement>(null);
  const idem = useRef<{ sig: string; key: string } | null>(null);
  const choiceName = useId();

  const keep = (next: Partial<Kept>) => store?.set(key, { note, picks, choice, ...next });

  // Focus starts in the note with the cursor at the end (C-SHEET-TEAMUP.a11y).
  useLayoutEffect(() => {
    const el = noteRef.current;
    if (!el) return;
    el.focus({ preventScroll: true });
    el.setSelectionRange(el.value.length, el.value.length);
  }, []);

  const hint = noteHint(note, data.drafted, data.min, data.max);
  const brought = draftId ? (choice === "merge" ? 1 : 0) : picks.length;
  const noteError = error?.field === "note" ? error.message : undefined;
  const bringError = error?.field === "brought_idea_ids" ? error.message : undefined;
  const sheetError = error && !noteError && !bringError ? error.message : undefined;

  const focusNote = () => {
    const el = noteRef.current;
    if (!el) return;
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
  };

  const send = async () => {
    if (busy) return;
    const merge = Boolean(draftId) && choice === "merge";
    const url = merge ? teamupUrls.mergeRequest(draftId!) : teamupUrls.send(ideaId);
    const body = merge
      ? { other_idea_id: ideaId, note }
      : draftId
        ? { note, brought_idea_ids: [], draft_id: draftId }
        : { note, brought_idea_ids: picks };
    // One key per request asked for: a retry of the same request reuses it, a changed one gets a new key (BLD-F026).
    const sig = `${url}|${JSON.stringify(body)}`;
    if (idem.current?.sig !== sig) idem.current = { sig, key: newKey() };
    setBusy(true);
    setError(null);
    const r = await call(url, {
      method: "POST",
      headers: { "content-type": "application/json", [IDEMPOTENCY_HEADER]: idem.current.key },
      body: JSON.stringify(body),
    });
    setBusy(false);
    if (!r.ok) {
      setError(r.error);
      if (r.error.field === "note") focusNote();
      return;
    }
    let sent: TeamUpSent;
    if (merge) {
      const m = (r.body ?? {}) as DraftMergeRequestState;
      sent = {
        kind: "merge",
        id: m.id ?? "",
        ideaId,
        note: m.note ?? note,
        brought: draftTitle ? [draftTitle] : [],
        after: m.after ?? null,
      };
    } else if (isRequest(r.body)) {
      sent = fromRequest(ideaId, { ...r.body, request: "teamup" }, r.body.after ?? null);
    } else {
      sent = { kind: "teamup", id: "", ideaId, note, brought: [], after: null };
    }
    store?.delete(key);
    // F-MOTION.inside: the spark marks the send, from the button that made it.
    if (sendRef.current?.isConnected) sparkBurst(sendRef.current);
    onSentHere(sent);
  };

  return (
    <>
      <h2 id={titleId} className="tus-h">
        {TEAMUP_COPY.title(first)}
      </h2>
      <p id={lineId} className="tus-p">
        {TEAMUP_COPY.line(first, data.title)}
      </p>

      <div className="tus-sec">
        <Field
          label={TEAMUP_COPY.noteLabel(first)}
          multiline
          help={!noteError && (hint.kind === "drafted" || hint.kind === "good") ? hint.text : undefined}
          warning={!noteError && !hint.ok ? hint.text : undefined}
          error={noteError}
        >
          {(control) => (
            <textarea
              {...control}
              ref={noteRef}
              rows={4}
              value={note}
              onChange={(e) => {
                setNote(e.target.value);
                keep({ note: e.target.value });
                if (error?.field === "note") setError(null);
              }}
            />
          )}
        </Field>
      </div>

      {draftId ? (
        <fieldset className="tus-choice">
          <legend className="lbl">{TEAMUP_COPY.draftChoice}</legend>
          <ChoiceRow
            name={choiceName}
            value="merge"
            checked={choice === "merge"}
            title={TEAMUP_COPY.merge(first)}
            help={TEAMUP_COPY.mergeHelp(first)}
            onPick={() => {
              setChoice("merge");
              keep({ choice: "merge" });
            }}
          />
          <ChoiceRow
            name={choiceName}
            value="separate"
            checked={choice === "separate"}
            title={TEAMUP_COPY.separate}
            help={TEAMUP_COPY.separateHelp}
            onPick={() => {
              setChoice("separate");
              keep({ choice: "separate" });
            }}
          />
        </fieldset>
      ) : (
        <div className="tus-sec">
          <Dropdown
            label={TEAMUP_COPY.bring}
            optional
            noun={{ one: "idea", many: "ideas" }}
            options={data.own.map((o) => ({ value: o.id, title: o.title, meta: o.meta }))}
            values={picks}
            onChange={(v) => {
              setPicks(v);
              keep({ picks: v });
              if (error?.field === "brought_idea_ids") setError(null);
            }}
            empty={TEAMUP_COPY.bringNone}
          />
          {bringError ? <FieldMsg>{bringError}</FieldMsg> : null}
        </div>
      )}

      <p className="tus-priv">{TEAMUP_COPY.privacy(first, brought)}</p>
      {sheetError ? <FieldMsg>{sheetError}</FieldMsg> : null}

      <div className="tus-f">
        <Button
          ref={sendRef}
          variant="primary"
          disabled={!hint.ok}
          onDisabledClick={focusNote}
          busy={busy}
          busyLabel={TEAMUP_COPY.sending}
          onClick={() => void send()}
        >
          {TEAMUP_COPY.send(first)}
        </Button>
      </div>
    </>
  );
}

function ChoiceRow({
  name,
  value,
  checked,
  title,
  help,
  onPick,
}: {
  name: string;
  value: Choice;
  checked: boolean;
  title: string;
  help: string;
  onPick(): void;
}) {
  const id = useId();
  return (
    <label className="tus-o" htmlFor={id}>
      <input
        id={id}
        type="radio"
        name={name}
        value={value}
        checked={checked}
        onChange={onPick}
        aria-labelledby={`${id}-t`}
        aria-describedby={`${id}-m`}
      />
      <span className="tus-ot">
        <span id={`${id}-t`} className="tus-on">
          {title}
        </span>
        <span id={`${id}-m`} className="tus-om">
          {help}
        </span>
      </span>
    </label>
  );
}

function newKey(): string {
  const c = globalThis.crypto as Crypto | undefined;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

// ---------------------------------------------------------------------------------------------------------------
// Step 2: sent (C-SHEET-TEAMUP.sent). The dialog keeps its name, "Team up with {lead}"; the new step is announced.
// ---------------------------------------------------------------------------------------------------------------
function SentBody({
  sent,
  first,
  titleId,
  lineId,
  doneLabel,
  onClose,
  onWithdrawnHere,
}: TeamUpSheetProps & {
  sent: TeamUpSent;
  first: string;
  titleId: string;
  lineId: string;
  onWithdrawnHere(sent: TeamUpSent): void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<SheetError | null>(null);
  const doneRef = useRef<HTMLButtonElement>(null);

  useLayoutEffect(() => {
    doneRef.current?.focus({ preventScroll: true });
  }, []);

  const withdraw = async () => {
    if (busy || !sent.id) return;
    setBusy(true);
    setError(null);
    const r = await withdrawRequest(sent.id);
    setBusy(false);
    if (!r.ok) {
      setError(r.error);
      return;
    }
    onWithdrawnHere({ ...sent, after: r.after });
  };

  const brought = useMemo(() => sent.brought.filter(Boolean), [sent.brought]);

  return (
    <>
      <span id={titleId} className="vh">
        {TEAMUP_COPY.title(first)}
      </span>
      <div className="tus-done" role="status">
        <span className="tus-ok" aria-hidden="true">
          <CheckIcon />
        </span>
        <h2 className="tus-h">{TEAMUP_COPY.sentTitle(first)}</h2>
        <p id={lineId} className="tus-p">
          {TEAMUP_COPY.sentLine(first)}
        </p>
        <div className="tus-sum">
          <h3 className="tus-l">{TEAMUP_COPY.yourNote}</h3>
          <p className="tus-q">{sent.note}</p>
          {brought.length ? (
            <p className="tus-sb">
              <LinkIcon />
              <span>{TEAMUP_COPY.bringing(brought)}</span>
            </p>
          ) : null}
        </div>
      </div>
      {error ? <FieldMsg>{error.message}</FieldMsg> : null}
      <div className="tus-f">
        {/* Withdraw needs the request's id; a reply without one leaves only the way on (BLD-F074). */}
        {sent.id ? (
          <Button
            variant="text"
            busy={busy}
            busyLabel={TEAMUP_COPY.withdrawing}
            onClick={() => void withdraw()}
          >
            {TEAMUP_COPY.withdraw}
          </Button>
        ) : null}
        <Button ref={doneRef} variant="primary" onClick={onClose}>
          {doneLabel ?? TEAMUP_COPY.done}
        </Button>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------------------------------------------
// The host helper: two lines on any screen that offers Team up.
// ---------------------------------------------------------------------------------------------------------------
export type TeamUpSheetOptions = Omit<TeamUpSheetProps, "ideaId" | "open" | "onClose"> & { onClose?(): void };

/**
 * `const teamUp = useTeamUpSheet({ onSent: refresh });` then `{teamUp.sheet}` in the page and
 * `onPrimary={teamUp.open}` on C-PREVIEW (or `onClick={() => teamUp.open(id)}` on a "Team up on …" button).
 */
export function useTeamUpSheet(options: TeamUpSheetOptions = {}): {
  open(ideaId: string): void;
  close(): void;
  isOpen: boolean;
  sheet: JSX.Element;
} {
  const [ideaId, setIdeaId] = useState<string | null>(null);
  const latest = useRef(options);
  useEffect(() => {
    latest.current = options;
  });
  const open = useCallback((id: string) => setIdeaId(id), []);
  const close = useCallback(() => {
    setIdeaId(null);
    latest.current.onClose?.();
  }, []);
  const { onClose: _ignored, ...rest } = options;
  void _ignored;
  const sheet = <TeamUpSheet {...rest} ideaId={ideaId ?? ""} open={ideaId !== null} onClose={close} />;
  return { open, close, isOpen: ideaId !== null, sheet };
}

// ---------------------------------------------------------------------------------------------------------------
// Icons (decorative)
// ---------------------------------------------------------------------------------------------------------------
function CloseIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg
      width="26"
      height="26"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1" />
      <path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1" />
    </svg>
  );
}
