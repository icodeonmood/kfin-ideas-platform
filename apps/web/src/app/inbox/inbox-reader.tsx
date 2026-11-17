"use client";

/**
 * C-INBOX-READER on S-H5: the list on the left, grouped Today / This week / Earlier, and the open item on the right
 * with its actions pinned to the foot. On a phone the list is the screen and an item opens as its own screen.
 *
 * Words come from the worker (HR-signed templates). A question, a decision's reason or a request's note is never
 * part of an item: the reader fetches it from its own owner's route when the item is opened, so it is read in the
 * app only (L-NOTIFY/3, BLD-E004). Everything is shown as text; nothing from a message becomes markup.
 */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

import type { InboxTab } from "@/lib/contracts";
import type { Action, InboxCounts, InboxEntry, InboxList } from "@/server/inbox";

const TAB_LABELS: Record<InboxTab, string> = {
  all: "All",
  needs_you: "Needs you",
  unread: "Unread",
  archived: "Archived",
};
const ORDER: InboxTab[] = ["all", "needs_you", "unread", "archived"];
const POLL_MS = 30_000;
const IST = "Asia/Kolkata";

type Group = "Today" | "This week" | "Earlier";

function dayKey(d: Date): string {
  return d.toLocaleDateString("en-CA", { timeZone: IST });
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

/** "11:20 am" today, "Sun, 15 Nov" this week, "2 Nov" before (C-INBOX-READER.row). */
export function whenLabel(iso: string, now: Date): string {
  const d = new Date(iso);
  const days = daysAgo(iso, now);
  if (days <= 0) {
    return d
      .toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", hour12: true, timeZone: IST })
      .replace(/\s?([AP])M$/i, (_m, p: string) => ` ${p.toLowerCase()}m`);
  }
  if (days < 7) {
    const wd = d.toLocaleDateString("en-GB", { weekday: "short", timeZone: IST });
    return `${wd}, ${d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: IST })}`;
  }
  const sameYear = d.getUTCFullYear() === now.getUTCFullYear();
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    ...(sameYear ? {} : { year: "numeric" }),
    timeZone: IST,
  });
}

function dueTone(label: string): string {
  if (label === "Overdue") return "over";
  return /hour/.test(label) ? "soon" : "";
}

function initialsOf(item: InboxEntry): string {
  return item.from === "system" ? "1%" : item.from.initials;
}

function titleOf(item: InboxEntry): string {
  return item.idea?.title ?? "";
}

/** The row's accessible name, as on the board: "Meera from the review desk asked you 3 questions, <title>, 11:20
 * am, unread". */
function rowName(item: InboxEntry, now: Date): string {
  const parts = [`${item.body.sender} ${item.line}`, titleOf(item), whenLabel(item.at, now)];
  if (item.unread) parts.push("unread");
  return parts.filter(Boolean).join(", ");
}

function Avatar({ item, size }: { item: InboxEntry; size: "sm" | "md" }) {
  return (
    <span className={`ibx-av ibx-av-${size}${item.from === "system" ? " sys" : ""}`} aria-hidden="true">
      {initialsOf(item)}
    </span>
  );
}

function Due({ item, small }: { item: InboxEntry; small?: boolean }) {
  if (!item.due) return null;
  return <span className={`ibx-due ${dueTone(item.due.label)}${small ? " xs" : ""}`}>{item.due.label}</span>;
}

type Detail =
  | { kind: "questions"; questions: string[]; due?: string }
  | { kind: "reason"; reason: string }
  | null;

/** The words that belong to the item, from the route that owns them (lane B's question set and decision). Missing
 * or refused: the reader shows the item's note instead. */
async function fetchDetail(item: InboxEntry): Promise<Detail> {
  const ref = item.idea?.id;
  if (!ref || !/^IDEA-\d{4}-\d{6}$/.test(ref)) return null;
  try {
    if (item.kind === "questions" || item.kind === "answer_reminder") {
      const res = await fetch(`/api/ideas/${ref}/question-set`, { cache: "no-store" });
      if (!res.ok) return null;
      const data = (await res.json()) as { questions?: { text?: unknown }[]; set?: { questions?: { text?: unknown }[] } };
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

function Footer({
  item,
  busy,
  onOp,
}: {
  item: InboxEntry;
  busy: boolean;
  onOp: (action: Action) => void;
}) {
  if (!item.actions.length) return null;
  return (
    <div className="ibx-bar">
      <div className="ibx-bar-in">
        {item.actions.map((a) => {
          const cls = `btn ${a.style === "primary" ? "btn-primary" : a.style === "text" ? "btn-quiet" : "btn-secondary"}`;
          if (a.to) {
            return (
              <Link key={`${a.label}-${a.to}`} className={cls} href={a.to}>
                {a.label}
              </Link>
            );
          }
          return (
            <button key={`${a.label}-${a.op}`} type="button" className={cls} disabled={busy} onClick={() => onOp(a)}>
              {a.label}
            </button>
          );
        })}
      </div>
    </div>
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
  const [tab, setTab] = useState<InboxTab>(initialTab);
  const [items, setItems] = useState<InboxEntry[]>(initial.items);
  const [counts, setCounts] = useState<InboxCounts>(initial.counts);
  const [openId, setOpenId] = useState<string | null>(initialItem);
  const [query, setQuery] = useState("");
  const [phoneOpen, setPhoneOpen] = useState(initialItem !== null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const [notice, setNotice] = useState<string>("");
  const [detail, setDetail] = useState<Detail>(null);
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const listRef = useRef<HTMLDivElement>(null);
  const known = useRef(new Set(initial.items.map((i) => i.id)));

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) => `${i.body.sender} ${i.line} ${titleOf(i)}`.toLowerCase().includes(q));
  }, [items, query]);

  const open = shown.find((i) => i.id === openId) ?? null;
  const position = open ? shown.indexOf(open) : -1;

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
    setNow(new Date());
    if (quiet && arrived.length) setFresh(new Set(arrived)); // one soft wash on what arrived (S-H5.rules/5)
    if (!quiet) setNotice("");
  }, []);

  // New items arrive at the top of Today while the page is open.
  useEffect(() => {
    const t = setInterval(() => {
      if (document.visibilityState === "visible") void load(tab, true);
    }, POLL_MS);
    return () => clearInterval(t);
  }, [load, tab]);

  const markRead = useCallback(async (item: InboxEntry) => {
    if (!item.unread) return;
    setItems((all) => all.map((x) => (x.id === item.id ? { ...x, unread: false } : x)));
    const res = await fetch(`/api/inbox/${item.id}/read`, { method: "POST" }).catch(() => null);
    if (res?.ok) setCounts((await res.json()) as InboxCounts); // every count changes at once (S-H5.rules/4)
  }, []);

  const select = useCallback(
    (item: InboxEntry, toPhone = true) => {
      setOpenId(item.id);
      setNotice("");
      if (toPhone) setPhoneOpen(true);
      void markRead(item);
    },
    [markRead],
  );

  // The first item of the tab is open by default on desktop (S-H5.rules/2).
  useEffect(() => {
    if (openId && shown.some((i) => i.id === openId)) return;
    const first = shown[0];
    const desktop = typeof window !== "undefined" && window.matchMedia("(min-width: 760px)").matches;
    if (first && desktop) select(first, false);
    else if (!first) setOpenId(null);
  }, [shown, openId, select]);

  useEffect(() => {
    let live = true;
    setDetail(null);
    if (open) void fetchDetail(open).then((d) => live && setDetail(d));
    return () => {
      live = false;
    };
    // Only when a different item opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open?.id]);

  async function changeTab(next: InboxTab) {
    if (next === tab) return;
    setTab(next);
    setOpenId(null);
    setPhoneOpen(false);
    await load(next);
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
    const at = rows.indexOf(document.activeElement as HTMLButtonElement);
    const next = rows[Math.max(0, Math.min(rows.length - 1, at + (e.key === "ArrowDown" ? 1 : -1)))];
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
    setCounts((await res.json()) as InboxCounts);
    await load(tab, true);
  }

  async function markUnread(item: InboxEntry) {
    const res = await fetch(`/api/inbox/${item.id}/unread`, { method: "POST" }).catch(() => null);
    if (!res?.ok) return;
    setCounts((await res.json()) as InboxCounts);
    setItems((all) => all.map((x) => (x.id === item.id ? { ...x, unread: true } : x)));
  }

  async function archive(item: InboxEntry) {
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
    setCounts((await res.json()) as InboxCounts);
    const rest = shown.filter((x) => x.id !== item.id);
    setItems((all) => (tab === "archived" ? all : all.filter((x) => x.id !== item.id)));
    const next = rest[Math.min(position, rest.length - 1)];
    setOpenId(next?.id ?? null);
    if (!next) setPhoneOpen(false);
  }

  async function runOp(item: InboxEntry, action: Action) {
    if (!action.op) return;
    setBusy(true);
    const res = await fetch(`/api/inbox/${item.id}/actions/${action.op}`, { method: "POST" }).catch(() => null);
    setBusy(false);
    if (!res?.ok) {
      const body = (await res?.json().catch(() => null)) as { error?: { message?: string } } | null;
      setNotice(body?.error?.message ?? "We couldn't do that just now. Please try again in a minute.");
      return;
    }
    await load(tab, true);
  }

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

  return (
    <div className={`ibx${phoneOpen && open ? " ibx-reading" : ""}`}>
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
            <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">
              <path d="M2.5 10.5l3.5 3.5 7-8M9 13.5l.5.5 7-8" fill="none" stroke="currentColor" strokeWidth="1.6" />
            </svg>
          </button>
        </div>
        <div className="ibx-search">
          <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" focusable="false">
            <circle cx="9" cy="9" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
            <path d="M13 13l4 4" stroke="currentColor" strokeWidth="1.6" />
          </svg>
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
          {groups.map((g) => (
            <div key={g.name} role="group" aria-labelledby={`ibx-g-${g.name.replace(" ", "-")}`}>
              <h2 id={`ibx-g-${g.name.replace(" ", "-")}`} className="ibx-grp">
                {g.name}
              </h2>
              {g.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`ibx-row${item.unread ? " un" : ""}${item.id === openId ? " sel" : ""}${fresh.has(item.id) ? " fresh" : ""}`}
                  aria-pressed={item.id === openId}
                  aria-label={rowName(item, now)}
                  onClick={() => select(item)}
                >
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
          ))}
        </div>
      </section>

      <section className="ibx-read" aria-label="Reader">
        {open ? (
          <>
            <div className="ibx-tool">
              <div className="ibx-tg">
                <button type="button" className="ibx-icon ibx-back" onClick={() => setPhoneOpen(false)}>
                  <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">
                    <path d="M12.5 4.5L7 10l5.5 5.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
                  </svg>
                  <span>Inbox</span>
                </button>
                <button
                  type="button"
                  className="ibx-icon"
                  aria-label="Archive"
                  aria-disabled={open.needs_you || open.archived ? "true" : undefined}
                  onClick={() => (open.archived ? undefined : void archive(open))}
                >
                  <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">
                    <path d="M3 5h14v3H3zM4.5 8v8h11V8M8 11h4" fill="none" stroke="currentColor" strokeWidth="1.6" />
                  </svg>
                </button>
                <button type="button" className="ibx-icon" aria-label="Mark unread" onClick={() => void markUnread(open)}>
                  <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">
                    <rect x="3" y="5" width="14" height="10" rx="2" fill="none" stroke="currentColor" strokeWidth="1.6" />
                    <path d="M3.5 6l6.5 5 6.5-5" fill="none" stroke="currentColor" strokeWidth="1.6" />
                  </svg>
                </button>
              </div>
              <div className="ibx-tg">
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
                  <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">
                    <path d="M5 12.5L10 7.5l5 5" fill="none" stroke="currentColor" strokeWidth="1.8" />
                  </svg>
                </button>
                <button
                  type="button"
                  className="ibx-icon"
                  aria-label="Next"
                  disabled={position >= shown.length - 1}
                  onClick={() => step(1)}
                >
                  <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false">
                    <path d="M5 7.5l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="1.8" />
                  </svg>
                </button>
              </div>
            </div>
            <p className="ibx-notice" role="status">
              {notice}
            </p>
            <article className="ibx-body" aria-labelledby="ibx-title">
              <div className="ibx-msg">
                <p className="ibx-kind">{open.body.heading}</p>
                <h2 id="ibx-title" className="ibx-mtitle">
                  {titleOf(open) || open.line}
                </h2>
                <div className="ibx-from">
                  <Avatar item={open} size="md" />
                  <span>
                    <span className="ibx-fl">
                      <b>{open.body.sender}</b> {open.line}
                    </span>
                    <span className="ibx-meta">{whenLabel(open.at, now)}</span>
                  </span>
                  <Due item={open} />
                </div>
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
                {(open.body.paragraphs ?? []).map((p, i) => (
                  <p key={i} className="ibx-para">
                    {p}
                  </p>
                ))}
                {open.body.note && detail?.kind !== "reason" ? <p className="ibx-foot">{open.body.note}</p> : null}
              </div>
            </article>
            <Footer item={open} busy={busy} onOp={(a) => void runOp(open, a)} />
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
