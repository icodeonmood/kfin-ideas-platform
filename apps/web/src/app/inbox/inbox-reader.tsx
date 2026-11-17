"use client";

/**
 * C-INBOX-READER on S-H5 (and S-H2B, a request open in it): the list on the left, grouped Today / This week /
 * Earlier, and the open item on the right with its actions pinned to the foot. On a phone the list is the screen
 * and an item opens as its own screen with a compact bar (S-H5.rules/6).
 *
 * Words come from the worker (HR-signed templates). A question, a decision's reason or a request's note is never
 * part of an item: the reader asks the route that owns it when the item is opened, so it is read in the app only
 * (L-NOTIFY/3, BLD-E004). Everything is shown as text; nothing from a message becomes markup.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from "react";

import type { InboxTab } from "@/lib/contracts";
import { COUNTS_EVENT } from "@/lib/inbox-events";
import type { Action, InboxCounts, InboxEntry, InboxList } from "@/server/inbox";

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

function dueTone(label: string): string {
  if (label === "Overdue") return "over";
  return /hour/i.test(label) ? "soon" : "";
}

function titleOf(item: InboxEntry): string {
  return item.idea?.title ?? "";
}

/** The row's accessible name, as on the board: "Meera from the review desk asked you 3 questions, <title>, 11:20
 * am, unread" (Inbox.md Controls). */
export function rowName(item: InboxEntry, now: Date): string {
  const parts = [`${item.body.sender} ${item.line}`, titleOf(item), whenLabel(item.at, now)];
  if (item.unread) parts.push("unread");
  return parts.filter(Boolean).join(", ");
}

function Avatar({ item, size }: { item: InboxEntry; size: "sm" | "md" }) {
  const system = item.from === "system";
  return (
    <span className={`ibx-av ibx-av-${size}${system ? " sys" : ""}`} aria-hidden="true">
      {item.from === "system" ? "1%" : item.from.initials}
    </span>
  );
}

function Due({ item, small }: { item: InboxEntry; small?: boolean }) {
  if (!item.due) return null;
  return <span className={`ibx-due ${dueTone(item.due.label)}${small ? " xs" : ""}`}>{item.due.label}</span>;
}

function btnClass(style: Action["style"]): string {
  return `btn ${style === "primary" ? "btn-primary" : style === "text" ? "btn-quiet" : "btn-secondary"}`;
}

type Detail = { kind: "questions"; questions: string[] } | { kind: "reason"; reason: string } | null;

/** The words that belong to the item, from the route that owns them (lane B's open question set and decision).
 * Missing or refused: the reader shows the item's own note. */
async function fetchDetail(item: InboxEntry): Promise<Detail> {
  const ref = item.idea?.id;
  if (!ref || !/^IDEA-\d{4}-\d{6}$/.test(ref)) return null;
  try {
    if ((item.kind === "questions" || item.kind === "answer_reminder") && item.needs_you) {
      const res = await fetch(`/api/ideas/${ref}/question-set`, { cache: "no-store" });
      if (!res.ok) return null;
      const data = (await res.json()) as {
        questions?: { text?: unknown }[];
        set?: { questions?: { text?: unknown }[] };
      };
      const qs = (data.questions ?? data.set?.questions ?? [])
        .map((q) => (typeof q.text === "string" ? q.text : ""))
        .filter(Boolean);
      return qs.length ? { kind: "questions", questions: qs } : null;
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

function ItemActions({ item, busy, onOp }: { item: InboxEntry; busy: boolean; onOp: (a: Action) => void }) {
  if (!item.actions.length) return null;
  return (
    <Footer>
      {item.actions.map((a) =>
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
  now,
  phone,
  notice,
  busy,
  titleRef,
  onOp,
  onAnswered,
  onNext,
}: {
  item: InboxEntry;
  now: Date;
  phone: boolean;
  notice: string;
  busy: boolean;
  titleRef: RefObject<HTMLHeadingElement | null>;
  onOp: (a: Action) => void;
  onAnswered: (item: InboxEntry) => void | Promise<void>;
  onNext: () => void;
}) {
  const [detail, setDetail] = useState<Detail>(null);
  useEffect(() => {
    let live = true;
    void fetchDetail(item).then((d) => live && setDetail(d));
    return () => {
      live = false;
    };
    // Once per item: the component is keyed by it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
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
                <b>{item.body.sender}</b> {item.line}
              </span>
              <span className="ibx-meta">{whenLabel(item.at, now)}</span>
            </span>
            <Due item={item} />
          </div>
          {request?.body}
          {detail?.kind === "questions" ? (
            <ol className="ibx-qs">
              {detail.questions.map((q, i) => (
                <li key={i}>
                  <span className="ibx-qn">Question {i + 1}</span>
                  <span className="ibx-qt">{q}</span>
                </li>
              ))}
            </ol>
          ) : null}
          {detail?.kind === "reason" ? <blockquote className="ibx-quote">{detail.reason}</blockquote> : null}
          {item.body.note ? <p className="ibx-foot">{item.body.note}</p> : null}
        </div>
      </article>
      {request ? request.bar : <ItemActions item={item} busy={busy} onOp={onOp} />}
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
  const router = useRouter();
  const [tab, setTab] = useState<InboxTab>(initialTab);
  const [items, setItems] = useState<InboxEntry[]>(initial.items);
  const [counts, setCounts] = useState<InboxCounts>(initial.counts);
  const [openId, setOpenId] = useState<string | null>(initialItem);
  const [query, setQuery] = useState("");
  const [phoneOpen, setPhoneOpen] = useState(initialItem !== null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const [notice, setNotice] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const listRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const known = useRef(new Set(initial.items.map((i) => i.id)));

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) => `${i.body.sender} ${i.line} ${titleOf(i)}`.toLowerCase().includes(q));
  }, [items, query]);

  const desktop = useDesktop();
  // The first item of the tab is open by default on desktop (S-H5.rules/2); a linked or chosen item opens anywhere.
  const chosen = shown.find((i) => i.id === openId) ?? null;
  const open = chosen ?? (desktop && !switching ? (shown[0] ?? null) : null);
  const position = open ? shown.indexOf(open) : -1;

  /** Every count on the page and in the shell changes at once (S-H5.rules/4, V-ACC.track/8). */
  const applyCounts = useCallback(
    (next: InboxCounts) => {
      setCounts(next);
      window.dispatchEvent(new CustomEvent(COUNTS_EVENT, { detail: next }));
      router.refresh();
    },
    [router],
  );

  const load = useCallback(async (next: InboxTab, quiet = false) => {
    const res = await fetch(`/api/inbox?tab=${next}`, { cache: "no-store" }).catch(() => null);
    if (!res?.ok) {
      if (!quiet) setNotice("We can't load your Inbox just now. Please try again in a minute.");
      return;
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
  }, []);

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
  }

  // Opening an item marks it read and every count comes back with it (L-INBOX.rules/3, S-H5.rules/4); not again
  // when it is marked unread while open. The first item opens by itself on a desktop only: the server renders the
  // desktop layout, so on a phone the first render may still hold it open, and it is not read until it is opened.
  useEffect(() => {
    if (!open?.unread) return;
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
  }, [open?.id]);

  // On a phone the item is its own screen: focus goes to its title, and back to its row on the way out.
  useEffect(() => {
    if (phoneOpen && open && !window.matchMedia(DESKTOP).matches) titleRef.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phoneOpen, open?.id]);

  function closePhone() {
    const id = openId;
    setPhoneOpen(false);
    requestAnimationFrame(() => document.getElementById(`ibx-row-${id}`)?.focus());
  }

  async function changeTab(next: InboxTab) {
    if (next === tab) return;
    setTab(next);
    setOpenId(null);
    setPhoneOpen(false);
    setSwitching(true);
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
            aria-label="Search your inbox"
            placeholder="Search your inbox"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
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
                        <span className="ibx-who">{item.body.sender}</span>
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
              now={now}
              phone={!desktop}
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
