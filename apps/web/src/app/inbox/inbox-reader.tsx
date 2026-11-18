"use client";

/**
 * C-INBOX-READER on S-H5 (and S-H2B, a request open in it): the list on the left, grouped Today / This week /
 * Earlier, and the open item on the right with its actions pinned to the foot. On a phone the list is the screen
 * and an item opens as its own screen with a compact bar (S-H5.rules/6).
 *
 * Words come from the worker (HR-signed templates). A question, a decision's reason or a request's note is never
 * part of an item: the reader asks the route that owns it when the item is opened, so it is read in the app only
 * (L-NOTIFY/3, BLD-E004). The desk's questions are lane B's card (C-QCARD, `variant="inbox"`), fed from the sharer's
 * question set. Everything is shown as text; nothing from a message becomes markup.
 *
 * The search filters in the browser and is never in the address (DEC-110): this tab keeps it for the history entry
 * (`lib/search-memory`), so a reload or Back brings it back and a link or a fresh visit starts without one.
 */
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from "react";

import { answerLabel, QuestionsCard } from "@/components/review/qcard";
import type { InboxTab, SharerQuestionSetResponse } from "@/lib/contracts";
import { COUNTS_EVENT } from "@/lib/inbox-events";
import { REVIEW_DESK_START } from "@/lib/review-desk";
import {
  cleanAddress,
  noSubscription,
  readSearch,
  replaceAddress,
  writeSearch,
  type SearchList,
} from "@/lib/search-memory";
import type { Action, InboxCounts, InboxEntry, InboxEntryKind, InboxList } from "@/server/inbox";

import { inboxHref, inboxSearch, isInboxPath, itemIn, readInboxAddress, type InboxView } from "./address";
import { useRequest } from "./teamup-request";

export { COUNTS_EVENT };

const TAB_LABELS: Record<InboxTab, string> = {
  all: "All",
  needs_you: "Needs you",
  unread: "Unread",
  archived: "Archived",
};
const ORDER: InboxTab[] = ["all", "needs_you", "unread", "archived"];
const POLL_MS = 30_000;
const DESKTOP = "(min-width: 760px)";

type Group = "Today" | "This week" | "Earlier";

function dayKey(d: Date): string {
  return d.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
}

function daysAgo(iso: string, now: Date): number {
  return Math.round((Date.parse(dayKey(now)) - Date.parse(dayKey(new Date(iso)))) / 86_400_000);
}

/** L-INBOX.rules/4. */
export function groupOf(iso: string, now: Date): Group {
  const days = daysAgo(iso, now);
  if (days <= 0) return "Today";
  return days < 7 ? "This week" : "Earlier";
}

/** "Just now", "11:20 am" today, "Sun, 15 Nov" this week, "2 Nov" before (C-INBOX-READER.row, S-H2B.reader/1). */
export function whenLabel(iso: string, now: Date): string {
  const d = new Date(iso);
  const days = daysAgo(iso, now);
  if (days <= 0) {
    if (now.getTime() - d.getTime() < 60_000) return "Just now";
    return d
      .toLocaleTimeString("en-IN", {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
        timeZone: "Asia/Kolkata",
      })
      .replace(/\s?([AP])M$/i, (_m, p: string) => ` ${p.toLowerCase()}m`);
  }
  if (days < 7) {
    const wd = d.toLocaleDateString("en-GB", { weekday: "short", timeZone: "Asia/Kolkata" });
    return `${wd}, ${d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" })}`;
  }
  const sameYear = dayKey(d).slice(0, 4) === dayKey(now).slice(0, 4);
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    ...(sameYear ? {} : { year: "numeric" }),
    timeZone: "Asia/Kolkata",
  });
}

/** The countdown's pill, as the worker counts it (F-COPY.plurals/3, BLD-A225): warn under a day ("07:38 left"), bad
 * once late ("Overdue by 5 hours"). A date ("By Thu, 19 Nov") carries no variant and stays plain. */
function dueTone(due: NonNullable<InboxEntry["due"]>): string {
  if (due.variant === "bad") return "over";
  return due.variant === "warn" ? "soon" : "";
}

function titleOf(item: InboxEntry): string {
  return item.idea?.title ?? "";
}

/** DEC-111 (BLD-A221): the review desk's kinds come from the desk as a whole, whoever reads them, and the 1% Club's
 * own kinds name no one. The worker already sends them that way; the reader holds to it too, so no reviewer's name
 * or initials can show even from an item rendered before the change. */
const DESK_KINDS: ReadonlySet<InboxEntryKind> = new Set<InboxEntryKind>([
  "questions",
  "answer_reminder",
  "decision",
  "worth_revised",
  "desk_merge",
  "detail_hidden_by_desk",
]);
const SYSTEM_KINDS: ReadonlySet<InboxEntryKind> = new Set<InboxEntryKind>(["sent_to_desk"]);

/** The sender as the row and the reader show them: "The review desk" for a desk kind (DEC-111), else the worker's. */
export function senderOf(item: InboxEntry): string {
  return DESK_KINDS.has(item.kind) ? REVIEW_DESK_START : item.body.sender;
}

/** True when the sender is drawn with the mark, never a person's initials: the system, and the desk (DEC-111). */
export function drawsMark(item: InboxEntry): boolean {
  return item.from === "system" || DESK_KINDS.has(item.kind) || SYSTEM_KINDS.has(item.kind);
}

/** The row's accessible name, as on the board: "The review desk asked you 3 questions, <title>, 11:20 am, unread"
 * (Inbox.md Controls; DEC-111 names the desk where the board names Meera). */
export function rowName(item: InboxEntry, now: Date): string {
  const parts = [`${senderOf(item)} ${item.line}`, titleOf(item), whenLabel(item.at, now)];
  if (item.unread) parts.push("unread");
  return parts.filter(Boolean).join(", ");
}

export function Avatar({ item, size }: { item: InboxEntry; size: "sm" | "md" }) {
  const mark = drawsMark(item);
  return (
    <span className={`ibx-av ibx-av-${size}${mark ? " sys" : ""}`} aria-hidden="true">
      {mark || item.from === "system" ? "1%" : item.from.initials}
    </span>
  );
}

function Due({ item, small }: { item: InboxEntry; small?: boolean }) {
  if (!item.due) return null;
  return <span className={`ibx-due ${dueTone(item.due)}${small ? " xs" : ""}`}>{item.due.label}</span>;
}

function btnClass(style: Action["style"]): string {
  return `btn ${style === "primary" ? "btn-primary" : style === "text" ? "btn-quiet" : "btn-secondary"}`;
}

type QuestionSet = NonNullable<SharerQuestionSetResponse>;
type Detail = { kind: "questions"; set: QuestionSet } | { kind: "reason"; reason: string } | null;

/** The sharer's open set as `GET /ideas/:id/question-set` sends it, with what the card reads. The reviewer (`by`) is
 * not read: the sharer's set comes without one (DEC-111). */
function isSet(data: unknown): data is QuestionSet {
  const s = data as Partial<QuestionSet> | null;
  return (
    !!s &&
    typeof s.id === "string" &&
    typeof s.idea?.id === "string" &&
    typeof s.deadline === "string" &&
    typeof s.answered === "number" &&
    Array.isArray(s.questions) &&
    s.questions.length > 0 &&
    s.questions.every((q) => typeof q?.id === "string" && typeof q.text === "string")
  );
}

/** The words that belong to the item, from the route that owns them (lane B's open question set and decision).
 * Missing or refused: the reader shows the item's own note. The first read of a question set marks it seen for the
 * desk (L-QUESTIONS.clock/1), so it is read only when the person has the item open (`readOn`: not while a phone
 * hydrates the server's desktop layout), only while the item needs them, and only for the item's own set: the route
 * gets its `set_id` and answers 404, marking nothing, when the open set is another (BLD-B248). */
async function fetchDetail(item: InboxEntry, readOn: boolean): Promise<Detail> {
  const ref = item.idea?.id;
  if (!ref || !/^IDEA-\d{4}-\d{6}$/.test(ref)) return null;
  try {
    if (item.kind === "questions" || item.kind === "answer_reminder") {
      const setId = typeof item.body.set_id === "string" ? item.body.set_id : "";
      if (!readOn || !item.needs_you || !setId) return null;
      const res = await fetch(`/api/ideas/${ref}/question-set?set_id=${encodeURIComponent(setId)}`, {
        cache: "no-store",
      });
      if (!res.ok) return null;
      const set: unknown = await res.json();
      return isSet(set) && set.id === setId ? { kind: "questions", set } : null;
    }
    if (item.kind === "decision") {
      const res = await fetch(`/api/ideas/${ref}/decision`, { cache: "no-store" });
      if (!res.ok) return null;
      const data = (await res.json()) as { reason?: unknown; decision?: { reason?: unknown } };
      const reason = typeof data.reason === "string" ? data.reason : data.decision?.reason;
      return typeof reason === "string" && reason ? { kind: "reason", reason } : null;
    }
  } catch {
    return null;
  }
  return null;
}

function Footer({ children }: { children: ReactNode }) {
  return (
    <div className="ibx-bar">
      <div className="ibx-bar-in">{children}</div>
    </div>
  );
}

/** The set's own words on the item's forward action, which goes to the Answer screen: "Carry on answering" once some
 * are sent, gone once all are (C-QCARD.states). The card is the body; its button sits in the foot (S-H5.rules/3).
 * An answer reminder keeps its own words, "Answer the questions" (L-INBOX.kinds), while anything is left to answer,
 * and loses the action, as the questions do, once all are sent (BLD-A199, J-TRACK/6). */
export function questionActions(
  actions: Action[],
  set: Pick<QuestionSet, "state" | "answered">,
  kind: InboxEntry["kind"] = "questions",
): Action[] {
  const label = answerLabel(set);
  const forward = (a: Action): Action[] =>
    !label ? [] : kind === "answer_reminder" ? [a] : [{ ...a, label }];
  return actions.flatMap((a) => (a.to && /\/answer$/.test(a.to) ? forward(a) : [a]));
}

function ItemActions({
  actions,
  busy,
  onOp,
}: {
  actions: Action[];
  busy: boolean;
  onOp: (a: Action) => void;
}) {
  if (!actions.length) return null;
  return (
    <Footer>
      {actions.map((a) =>
        a.to ? (
          <Link key={`${a.label}-${a.to}`} className={btnClass(a.style)} href={a.to}>
            {a.label}
          </Link>
        ) : (
          <button
            key={`${a.label}-${a.op}`}
            type="button"
            className={btnClass(a.style)}
            disabled={busy}
            onClick={() => onOp(a)}
          >
            {a.label}
          </button>
        ),
      )}
    </Footer>
  );
}

const Icon = {
  readAll: (
    <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">
      <path d="M2.5 10.5l3.5 3.5 7-8M9 13.5l.5.5 7-8" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
  search: (
    <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" focusable="false">
      <circle cx="9" cy="9" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M13 13l4 4" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
  back: (
    <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">
      <path d="M12.5 4.5L7 10l5.5 5.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  ),
  archive: (
    <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">
      <path d="M3 5h14v3H3zM4.5 8v8h11V8M8 11h4" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
  unread: (
    <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">
      <rect x="3" y="5" width="14" height="10" rx="2" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3.5 6l6.5 5 6.5-5" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
  up: (
    <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">
      <path d="M5 12.5L10 7.5l5 5" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  ),
  down: (
    <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">
      <path d="M5 7.5l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  ),
};

/** Where this tab keeps the Inbox's search, on `/inbox` and `/inbox/:itemId` alike (DEC-110). */
const LIST: SearchList = "/inbox";

/** The view to start from. The page's props name the view its address had when the server rendered it; the address
 * itself (`useSearchParams`, the router's own) is where the person left it. They differ when Back restores the page
 * from the router's cache after the reader moved the address; that page, and any Inbox reached by Back or Forward,
 * loads the tab the address names again (`reload`) and opens its item once that list is in. Otherwise the two agree,
 * so a hydrated page renders exactly what the server did (P-ROUTES.state, J-BROWSE/4). The search starts empty, as
 * the server rendered it; the reader takes this tab's kept words once it has mounted (DEC-110). */
export function startView(
  address: Parameters<typeof readInboxAddress>[0],
  initial: { tab: InboxTab; item: string | null; items: readonly { id: string }[] },
  byHistory = false,
): InboxView & { reload: boolean } {
  const asked = readInboxAddress(address);
  const view = asked.named
    ? { tab: asked.tab, item: asked.item, q: "" }
    : { tab: initial.tab, item: initial.item, q: "" };
  // Back or Forward may bring a page the router rendered before the person read anything: load it again first
  if (byHistory || view.tab !== initial.tab) return { ...view, reload: true };
  return { ...view, item: asked.named ? itemIn(asked.item, initial.items) : initial.item, reload: false };
}

/** Set when the browser moves through history (Back or Forward) and cleared when an Inbox arrives, so an Inbox the
 * router brings back that way loads its list again before it opens anything (nothing stale is marked read). */
const moved = { byHistory: false };
if (typeof window !== "undefined") {
  window.addEventListener("popstate", () => {
    moved.byHistory = true;
  });
}

function subscribeDesktop(cb: () => void): () => void {
  const m = window.matchMedia(DESKTOP);
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
}

/** Whether the two panes sit side by side; the server renders the desktop layout. */
function useDesktop(): boolean {
  return useSyncExternalStore(
    subscribeDesktop,
    () => window.matchMedia(DESKTOP).matches,
    () => true,
  );
}

/** The open item: its words from the route that owns them, its request if it is one, and its actions at the foot.
 * Keyed by the item, so nothing from the last item carries over. On a phone the item is its own screen and the
 * list's h1 is hidden with the list, so the item's title is the screen's h1 (WCAG 2.1 AA, S-H5.rules/6). */
function OpenItem({
  item,
  ready,
  now,
  phone,
  phoneOpen,
  notice,
  busy,
  titleRef,
  onOp,
  onAnswered,
  onNext,
}: {
  item: InboxEntry;
  /** False while the page hydrates without the search this tab keeps (DEC-110), as for the mark-read effect */
  ready: boolean;
  now: Date;
  phone: boolean;
  phoneOpen: boolean;
  notice: string;
  busy: boolean;
  titleRef: RefObject<HTMLHeadingElement | null>;
  onOp: (a: Action) => void;
  onAnswered: (item: InboxEntry) => void | Promise<void>;
  onNext: () => void;
}) {
  const [detail, setDetail] = useState<Detail>(null);
  useEffect(() => {
    // As the mark-read effect: nothing is read while the page hydrates the unfiltered list, before the kept search is
    // back: the first read of a question set marks it seen for the desk (L-QUESTIONS.clock/1, DEC-110). Once that
    // search is in, an item it hides is no longer open; one it keeps reads now.
    if (!ready) return;
    let live = true;
    // On a phone an item is open only once the person opens it
    const readOn = phoneOpen || window.matchMedia(DESKTOP).matches;
    void fetchDetail(item, readOn).then((d) => live && setDetail(d));
    return () => {
      live = false;
    };
    // Once per item once ready: the component is keyed by it, and `ready` only ever turns true.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);
  const request = useRequest(item, onAnswered, onNext);
  const Title = phone ? "h1" : "h2";
  return (
    <>
      <article className="ibx-body" aria-labelledby="ibx-title">
        <div className="ibx-msg">
          <p className="ibx-notice" role="status">
            {notice}
          </p>
          <p className="ibx-kind">{item.body.heading}</p>
          <Title id="ibx-title" className="ibx-mtitle" ref={titleRef} tabIndex={-1}>
            {titleOf(item) || item.line}
          </Title>
          <div className="ibx-from">
            <Avatar item={item} size="md" />
            <span className="ibx-fw">
              <span className="ibx-fl">
                <b>{senderOf(item)}</b> {item.line}
              </span>
              <span className="ibx-meta">{whenLabel(item.at, now)}</span>
            </span>
            <Due item={item} />
          </div>
          {request?.body}
          {detail?.kind === "questions" ? (
            <QuestionsCard variant="inbox" ideaId={detail.set.idea.id} set={detail.set} />
          ) : null}
          {detail?.kind === "reason" ? <blockquote className="ibx-quote">{detail.reason}</blockquote> : null}
          {/* The card says the deadline from the set itself, so the item's own "Answer by" note would repeat it */}
          {item.body.note && detail?.kind !== "questions" ? (
            <p className="ibx-foot">{item.body.note}</p>
          ) : null}
        </div>
      </article>
      {request ? (
        request.bar
      ) : (
        <ItemActions
          actions={
            detail?.kind === "questions" ? questionActions(item.actions, detail.set, item.kind) : item.actions
          }
          busy={busy}
          onOp={onOp}
        />
      )}
    </>
  );
}

export function InboxReader({
  initial,
  initialTab,
  initialItem,
}: {
  initial: InboxList;
  initialTab: InboxTab;
  initialItem: string | null;
}) {
  const address = useSearchParams();
  const [start] = useState(() =>
    startView(address, { tab: initialTab, item: initialItem, items: initial.items }, moved.byHistory),
  );
  const [tab, setTab] = useState<InboxTab>(start.tab);
  const [items, setItems] = useState<InboxEntry[]>(initial.items);
  const [counts, setCounts] = useState<InboxCounts>(initial.counts);
  // While the address's own tab loads, nothing is open, so nothing from the cached list is marked read.
  const [openId, setOpenId] = useState<string | null>(start.reload ? null : start.item);
  // The search: what the person typed here, else the words this tab keeps for the entry (DEC-110). The server and the
  // hydrating render have none; the next render reads them
  const kept = useSyncExternalStore(
    noSubscription,
    () => readSearch(LIST),
    () => start.q,
  );
  const [typed, setTyped] = useState<string | null>(null);
  const query = typed ?? kept;
  const [phoneOpen, setPhoneOpen] = useState(!start.reload && start.item !== null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const [notice, setNotice] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [switching, setSwitching] = useState(start.reload);
  const [now, setNow] = useState(() => new Date());
  const listRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const known = useRef(new Set(initial.items.map((i) => i.id)));
  const view = useRef<InboxView>({ tab: start.tab, item: start.item, q: start.q });
  const wrote = useRef(false);
  // False while the page hydrates without the search this tab keeps: nothing is marked read from the unfiltered list
  // before it is back (DEC-110)
  const ready = useSyncExternalStore(
    noSubscription,
    () => true,
    () => false,
  );
  useLayoutEffect(() => {
    cleanAddress();
  }, []);
  useEffect(() => {
    view.current = { ...view.current, q: query };
  }, [query]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) => `${senderOf(i)} ${i.line} ${titleOf(i)}`.toLowerCase().includes(q));
  }, [items, query]);

  const desktop = useDesktop();
  // The first item of the tab is open by default on desktop (S-H5.rules/2); a linked or chosen item opens anywhere.
  const chosen = shown.find((i) => i.id === openId) ?? null;
  const open = chosen ?? (desktop && !switching ? (shown[0] ?? null) : null);
  const position = open ? shown.indexOf(open) : -1;

  /** Every count on the page and in the shell changes at once (S-H5.rules/4, V-ACC.track/8): the shell hears them
   * on COUNTS_EVENT and fetches its own number again on every navigation. No `router.refresh` here: one still running
   * when the person opens a link from the item leaves Next's history entry for the Inbox half-written, and Back then
   * changes the address but keeps the page the person left (BLD-A198, gates run 44226165244). */
  const applyCounts = useCallback((next: InboxCounts) => {
    setCounts(next);
    window.dispatchEvent(new CustomEvent(COUNTS_EVENT, { detail: next }));
  }, []);

  const load = useCallback(async (next: InboxTab, quiet = false): Promise<InboxList | null> => {
    const res = await fetch(`/api/inbox?tab=${next}`, { cache: "no-store" }).catch(() => null);
    if (!res?.ok) {
      if (!quiet) setNotice("We can't load your Inbox just now. Please try again in a minute.");
      return null;
    }
    const data = (await res.json()) as InboxList;
    const arrived = data.items.filter((i) => !known.current.has(i.id)).map((i) => i.id);
    data.items.forEach((i) => known.current.add(i.id));
    setItems(data.items);
    setCounts(data.counts);
    // The 30 s refresh and a tab change bring every count; the shell's Inbox number moves with them.
    window.dispatchEvent(new CustomEvent(COUNTS_EVENT, { detail: data.counts }));
    setNow(new Date());
    if (quiet && arrived.length) setFresh(new Set(arrived)); // one soft wash on what arrived (S-H5.rules/5)
    if (!quiet) setNotice("");
    return data;
  }, []);

  /** The tab and the open item go into the address at once with `history.replaceState`, as on the review desk
   * (BLD-B253): no navigation, no history entry, and Back from what the person opens comes here again. The search
   * goes into this tab's memory of the same entry, never the address (DEC-110); the two merge into the entry's state,
   * so neither wipes the other. Written only while the Inbox is the page; a browser that limits how often history may
   * be written keeps the last one. */
  const remember = useCallback((change: Partial<InboxView>) => {
    view.current = { ...view.current, ...change };
    if (!isInboxPath(window.location.pathname)) return;
    wrote.current = true;
    writeSearch(LIST, view.current.q);
    const href = inboxHref(window.location.pathname, view.current);
    if (window.location.pathname + window.location.search === href) return;
    replaceAddress(href);
  }, []);

  // The router can put back an address from an update it started before the person moved (its own state is written
  // to the address on every change). Once the reader has written the view, the address follows the screen again.
  useEffect(() => {
    if (wrote.current) remember({});
  }, [address, remember]);

  // Back to an Inbox the router kept from before: load the tab the address names, then open its item if it is still
  // in that list (J-BROWSE/4). Once, on arrival.
  useEffect(() => {
    moved.byHistory = false;
    if (!start.reload) return;
    let live = true;
    const later = setTimeout(() => {
      void load(start.tab).then((data) => {
        if (!live || view.current.tab !== start.tab) return; // the person has moved on meanwhile
        const item = data ? itemIn(start.item, data.items) : null;
        setOpenId(item);
        setPhoneOpen(item !== null);
        setSwitching(false);
        if (item !== start.item) remember({ item });
      });
    }, 0);
    return () => {
      live = false;
      clearTimeout(later);
    };
  }, [start, load, remember]);

  // New items arrive at the top of Today while the page is open (S-H5.rules/5).
  useEffect(() => {
    const t = setInterval(() => {
      if (document.visibilityState === "visible") void load(tab, true);
    }, POLL_MS);
    return () => clearInterval(t);
  }, [load, tab]);

  function select(item: InboxEntry, toPhone = true) {
    setOpenId(item.id);
    setNotice("");
    if (toPhone) setPhoneOpen(true);
    remember({ item: item.id });
  }

  // Opening an item marks it read and every count comes back with it (L-INBOX.rules/3, S-H5.rules/4); not again
  // when it is marked unread while open. The first item opens by itself on a desktop only: the server renders the
  // desktop layout, so on a phone the first render may still hold it open, and it is not read until it is opened.
  useEffect(() => {
    if (!ready || !open?.unread) return;
    if (!phoneOpen && !window.matchMedia(DESKTOP).matches) return;
    const id = open.id;
    void fetch(`/api/inbox/${id}/read`, { method: "POST" })
      .then(async (res) => {
        if (!res.ok) return;
        setItems((all) => all.map((x) => (x.id === id ? { ...x, unread: false } : x)));
        applyCounts((await res.json()) as InboxCounts);
      })
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open?.id, ready]);

  // On a phone the item is its own screen: focus goes to its title, and back to its row on the way out.
  useEffect(() => {
    if (phoneOpen && open && !window.matchMedia(DESKTOP).matches) titleRef.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phoneOpen, open?.id]);

  function closePhone() {
    const id = openId;
    setPhoneOpen(false);
    remember({ item: null });
    requestAnimationFrame(() => document.getElementById(`ibx-row-${id}`)?.focus());
  }

  async function changeTab(next: InboxTab) {
    if (next === tab) return;
    setTab(next);
    setOpenId(null);
    setPhoneOpen(false);
    setSwitching(true);
    remember({ tab: next, item: null });
    await load(next);
    setSwitching(false);
  }

  function onTabKey(e: KeyboardEvent<HTMLButtonElement>, index: number) {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = ORDER[(index + step + ORDER.length) % ORDER.length]!;
    document.getElementById(`ibx-tab-${next}`)?.focus();
    void changeTab(next);
  }

  /** Arrow keys move through the list; Enter opens (S-H5.rules/2). */
  function onListKey(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const rows = Array.from(listRef.current?.querySelectorAll<HTMLButtonElement>("button.ibx-row") ?? []);
    if (!rows.length) return;
    const at = rows.indexOf(document.activeElement as HTMLButtonElement);
    const to = at < 0 ? 0 : at + (e.key === "ArrowDown" ? 1 : -1);
    const next = rows[Math.max(0, Math.min(rows.length - 1, to))];
    if (next) {
      e.preventDefault();
      next.focus();
    }
  }

  /** The list filters as the person types, and this tab keeps the words at once, so Back from a link opened straight
   * after brings them back (DEC-110). */
  function search(value: string) {
    const q = inboxSearch(value);
    setTyped(q);
    remember({ q });
  }

  function step(by: number) {
    const next = shown[position + by];
    if (next) select(next, false);
  }

  async function markAllRead() {
    if (!counts.unread) return;
    const res = await fetch("/api/inbox/read-all", { method: "POST" }).catch(() => null);
    if (!res?.ok) return;
    applyCounts((await res.json()) as InboxCounts);
    setItems((all) => all.map((x) => ({ ...x, unread: false })));
  }

  async function markUnread(item: InboxEntry) {
    const res = await fetch(`/api/inbox/${item.id}/unread`, { method: "POST" }).catch(() => null);
    if (!res?.ok) return;
    applyCounts((await res.json()) as InboxCounts);
    setItems((all) => all.map((x) => (x.id === item.id ? { ...x, unread: true } : x)));
  }

  async function archive(item: InboxEntry) {
    if (item.archived) return;
    if (item.needs_you) {
      setNotice("This still needs you, so it stays in your Inbox until it's done.");
      return;
    }
    const res = await fetch(`/api/inbox/${item.id}/archive`, { method: "POST" }).catch(() => null);
    if (!res?.ok) {
      const body = (await res?.json().catch(() => null)) as { error?: { message?: string } } | null;
      setNotice(body?.error?.message ?? "We couldn't archive that just now. Please try again in a minute.");
      return;
    }
    applyCounts((await res.json()) as InboxCounts);
    const rest = shown.filter((x) => x.id !== item.id);
    setItems((all) => all.filter((x) => x.id !== item.id));
    const next = rest[Math.min(position, rest.length - 1)];
    setOpenId(next?.id ?? null);
    if (!next) setPhoneOpen(false);
    remember({ item: next?.id ?? null });
  }

  async function runOp(item: InboxEntry, action: Action) {
    if (!action.op) return;
    setBusy(true);
    const res = await fetch(`/api/inbox/${item.id}/actions/${action.op}`, { method: "POST" }).catch(
      () => null,
    );
    setBusy(false);
    if (!res?.ok) {
      const body = (await res?.json().catch(() => null)) as { error?: { message?: string } } | null;
      setNotice(body?.error?.message ?? "We couldn't do that just now. Please try again in a minute.");
      return;
    }
    await load(tab, true);
  }

  /** A request answered from the reader leaves "Needs you" in place; the list keeps it so the result stays in
   * view (S-H2B.rules/2). */
  const onAnswered = useCallback(
    async (item: InboxEntry) => {
      setItems((all) => all.map((x) => (x.id === item.id ? { ...x, needs_you: false } : x)));
      const res = await fetch("/api/inbox/counts", { cache: "no-store" }).catch(() => null);
      if (res?.ok) applyCounts((await res.json()) as InboxCounts);
    },
    [applyCounts],
  );

  const groups = useMemo(() => {
    const out: { name: Group; items: InboxEntry[] }[] = [];
    for (const item of shown) {
      const name = groupOf(item.at, now);
      const last = out[out.length - 1];
      if (last && last.name === name) last.items.push(item);
      else out.push({ name, items: [item] });
    }
    return out;
  }, [shown, now]);

  const reading = phoneOpen && open !== null;

  return (
    <div className={`ibx${reading ? " ibx-reading" : ""}`}>
      <section className="ibx-list" aria-labelledby="ibx-h1">
        <div className="ibx-head">
          <h1 id="ibx-h1" className="ibx-h1">
            Inbox
          </h1>
          <span className="ibx-count" aria-live="polite">
            {counts.unread} unread
          </span>
          <button
            type="button"
            className="ibx-icon"
            aria-label="Mark all read"
            aria-disabled={counts.unread ? undefined : "true"}
            onClick={() => void markAllRead()}
          >
            {Icon.readAll}
          </button>
        </div>
        <div className="ibx-search">
          {Icon.search}
          <input
            type="search"
            autoComplete="off"
            aria-label="Search your inbox"
            placeholder="Search your inbox"
            value={query}
            onChange={(e) => search(e.target.value)}
          />
        </div>
        <div className="ibx-tabs" role="tablist" aria-label="Show">
          {ORDER.map((t, i) => (
            <button
              key={t}
              id={`ibx-tab-${t}`}
              type="button"
              role="tab"
              className="ibx-tab"
              aria-selected={tab === t}
              aria-controls="ibx-panel"
              tabIndex={tab === t ? 0 : -1}
              onClick={() => void changeTab(t)}
              onKeyDown={(e) => onTabKey(e, i)}
            >
              {TAB_LABELS[t]} <span className="ibx-cn">{counts[t]}</span>
            </button>
          ))}
        </div>
        <div
          id="ibx-panel"
          className="ibx-scroll"
          role="tabpanel"
          aria-labelledby={`ibx-tab-${tab}`}
          ref={listRef}
          onKeyDown={onListKey}
        >
          {groups.length === 0 ? <p className="ibx-empty">Nothing here.</p> : null}
          {groups.map((g) => {
            const gid = `ibx-g-${g.name.replace(" ", "-")}`;
            return (
              <div key={g.name} role="group" aria-labelledby={gid}>
                <h2 id={gid} className="ibx-grp">
                  {g.name}
                </h2>
                {g.items.map((item) => (
                  <button
                    key={item.id}
                    id={`ibx-row-${item.id}`}
                    type="button"
                    className={`ibx-row${item.unread ? " un" : ""}${item.id === open?.id ? " sel" : ""}${fresh.has(item.id) ? " fresh" : ""}`}
                    aria-pressed={item.id === open?.id}
                    onClick={() => select(item)}
                  >
                    {/* The name as the board reads it: "{sender} {what}, {title}, {when}, unread" (Inbox.md). */}
                    <span className="visually-hidden">{rowName(item, now)}</span>
                    <span className="ibx-udot" aria-hidden="true" />
                    <Avatar item={item} size="sm" />
                    <span className="ibx-b" aria-hidden="true">
                      <span className="ibx-top">
                        <span className="ibx-who">{senderOf(item)}</span>
                        <span className="ibx-when">{whenLabel(item.at, now)}</span>
                      </span>
                      <span className="ibx-title">{titleOf(item) || item.line}</span>
                      {titleOf(item) ? <span className="ibx-what">{item.line}</span> : null}
                      <Due item={item} small />
                    </span>
                  </button>
                ))}
              </div>
            );
          })}
        </div>
      </section>

      <section className="ibx-read" aria-label="Reader">
        {open ? (
          <>
            <div className="ibx-tool">
              <div className="ibx-tg">
                <button type="button" className="ibx-icon ibx-back" onClick={closePhone}>
                  {Icon.back}
                  <span>Inbox</span>
                </button>
                <button
                  type="button"
                  className="ibx-icon"
                  aria-label="Archive"
                  aria-disabled={open.needs_you || open.archived ? "true" : undefined}
                  onClick={() => void archive(open)}
                >
                  {Icon.archive}
                </button>
                <button
                  type="button"
                  className="ibx-icon"
                  aria-label="Mark unread"
                  onClick={() => void markUnread(open)}
                >
                  {Icon.unread}
                </button>
              </div>
              <div className="ibx-tg ibx-nav">
                <span className="ibx-pos">
                  {position + 1} of {shown.length}
                </span>
                <button
                  type="button"
                  className="ibx-icon"
                  aria-label="Previous"
                  disabled={position <= 0}
                  onClick={() => step(-1)}
                >
                  {Icon.up}
                </button>
                <button
                  type="button"
                  className="ibx-icon"
                  aria-label="Next"
                  disabled={position >= shown.length - 1}
                  onClick={() => step(1)}
                >
                  {Icon.down}
                </button>
              </div>
            </div>
            <OpenItem
              key={open.id}
              item={open}
              ready={ready}
              now={now}
              phone={!desktop}
              phoneOpen={phoneOpen}
              notice={notice}
              busy={busy}
              titleRef={titleRef}
              onOp={(a) => void runOp(open, a)}
              onAnswered={onAnswered}
              onNext={() => step(1)}
            />
          </>
        ) : (
          <div className="ibx-none">
            <p>Pick something on the left to read it here.</p>
            {notice ? (
              <p className="ibx-notice" role="status">
                {notice}
              </p>
            ) : null}
          </div>
        )}
      </section>
    </div>
  );
}
