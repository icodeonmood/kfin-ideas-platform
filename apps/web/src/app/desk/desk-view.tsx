"use client";

/**
 * S-R1 Review desk (L-REVIEW.queue): search, four tabs with counts, a sort, and one table whose rows carry every
 * running clock. Countdowns tick each minute without a reload (S-R1.rules/2); tab, sort and search are kept in the
 * URL (S-R1.rules/4); "Remind {sharer}" acts in place (S-R1.rules/3). On a phone the table becomes cards
 * (S-R1.rules/6).
 */
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button, ButtonLink } from "@/components/ui/button";
import { Empty } from "@/components/ui/empty";
import { Pill, type PillVariant } from "@/components/ui/pill";
import { SearchBar } from "@/components/ui/search";
import { Sorts } from "@/components/ui/sorts";
import { Tabs, tabPanelProps } from "@/components/ui/tabs";
import type { CountdownVariant, DeskResponse, DeskRow, DeskSort, DeskTab } from "@/lib/contracts";
import { countdown, countdownLabel, nextTickMs } from "@/lib/desk/countdown";
import { useFlipList } from "@/lib/motion/flip";

const TABS: { value: DeskTab; label: string }[] = [
  { value: "to_review", label: "To review" },
  { value: "waiting", label: "Waiting on the sharer" },
  { value: "answered", label: "Answered, back to you" },
  { value: "decided", label: "Decided this week" },
];
const SORT_OPTIONS: { value: DeskSort; label: string }[] = [
  { value: "time_left", label: "Time left" },
  { value: "decide_by", label: "Decide by" },
  { value: "area", label: "Area" },
];
const PILL: Record<CountdownVariant, PillVariant> = { normal: "neutral", warn: "warn", bad: "bad" };
const REMINDED = "Reminded, just now";
// Not drawn on the board (empty tabs): wording for HR's sign-off (docs/hr-wording/lane-b.md).
const EMPTY: Record<DeskTab, { title: string; line: string }> = {
  to_review: { title: "Nothing new to review", line: "Ideas shared with the review desk show here first." },
  waiting: {
    title: "No one is answering questions now",
    line: "When you ask a sharer something, its clock shows here.",
  },
  answered: { title: "No answers waiting", line: "Answers come back here as soon as a sharer sends them." },
  decided: {
    title: "Nothing decided this week",
    line: "Decisions stay here for seven days, with the Ones Committee’s window.",
  },
};

/** The time now, refreshed on each whole minute: every countdown label can only change then. */
function useMinute(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const tick = () => {
      setNow(new Date());
      timer = setTimeout(tick, nextTickMs());
    };
    timer = setTimeout(tick, nextTickMs());
    return () => clearTimeout(timer);
  }, []);
  return now;
}

function ClockIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8.5" r="5.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 5.5V8.5L10 10M6.5 1.75h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

/** The question dots (board Desk): one per question, filled once answered. The words beside them say the same. */
function Dots({ asked, answered }: { asked: number; answered: number }) {
  if (!asked) return null;
  return (
    <span className="rd-dots" aria-hidden="true">
      {Array.from({ length: asked }, (_, i) => (
        <i key={i} className={i < answered ? "on" : undefined} />
      ))}
    </span>
  );
}

function TimeLeft({ row, tab, now }: { row: DeskRow; tab: DeskTab; now: Date }) {
  if (!row.time_left) return null;
  const live = row.due_at ? countdown(row.due_at, now) : null;
  const label = live ? countdownLabel(live, tab === "waiting" ? "to answer" : "to decide") : row.time_left;
  const variant = live?.variant ?? row.variant ?? "normal";
  return (
    <Pill variant={PILL[variant]}>
      <ClockIcon />
      {label}
    </Pill>
  );
}

/** The tab, sort and search an address asks for, or null for any it does not name (S-R1.rules/4). */
function deskUrlState(search: string): { tab: DeskTab | null; sort: DeskSort | null; q: string } {
  const sp = new URLSearchParams(search);
  return {
    tab: TABS.find((t) => t.value === sp.get("tab"))?.value ?? null,
    sort: SORT_OPTIONS.find((s) => s.value === sp.get("sort"))?.value ?? null,
    q: (sp.get("q") ?? "").slice(0, 200),
  };
}

export function DeskView({ initial, initialQuery }: { initial: DeskResponse; initialQuery: string }) {
  const [data, setData] = useState(initial);
  // The tab and sort chosen, shown pressed at once while their list loads (C-TABS, C-SORTS).
  const [view, setView] = useState<{ tab: DeskTab; sort: DeskSort }>({
    tab: initial.tab,
    sort: initial.sort,
  });
  const [text, setText] = useState(initialQuery);
  const [query, setQuery] = useState(initialQuery);
  const [reminded, setReminded] = useState<Set<string>>(() => new Set());
  const [failed, setFailed] = useState<string | null>(null);
  const now = useMinute();
  const body = useRef<HTMLTableSectionElement>(null);
  const loading = useRef<AbortController | null>(null);
  useFlipList(body, `${data.tab}:${data.sort}:${data.items.map((r) => r.idea_id).join(",")}`);

  const load = useCallback(async (tab: DeskTab, sort: DeskSort, q: string) => {
    const params = new URLSearchParams({ tab, sort });
    if (q) params.set("q", q);
    setView({ tab, sort });
    // The address takes the tab, sort and search at once, without a navigation: a router navigation waits for the
    // server, and a row opened before it lands would leave Back on the old address (S-R1.rules/4, J-BROWSE/4).
    window.history.replaceState(null, "", `/desk?${params.toString()}`);
    loading.current?.abort();
    const ctl = new AbortController();
    loading.current = ctl;
    try {
      const res = await fetch(`/api/desk?${params.toString()}`, { signal: ctl.signal, cache: "no-store" });
      if (res.ok && loading.current === ctl) setData((await res.json()) as DeskResponse);
    } catch {
      // a newer request took over, or the network dropped; the table keeps what it had
    }
  }, []);

  // Back to the desk: the page may come from the router's cache for an older address, so the list follows the
  // address the person left, not the props (S-R1.rules/4).
  useEffect(() => {
    const want = deskUrlState(window.location.search);
    const tab = want.tab ?? initial.tab;
    const sort = want.sort ?? initial.sort;
    if (tab === initial.tab && sort === initial.sort && want.q === initialQuery) return;
    const frame = requestAnimationFrame(() => {
      setText(want.q);
      setQuery(want.q);
      void load(tab, sort, want.q);
    });
    return () => cancelAnimationFrame(frame);
  }, [initial, initialQuery, load]);

  // A reviewer coming back to the tab sees clocks and tabs as they are now (L-REVIEW.queue).
  useEffect(() => {
    const again = () => {
      if (document.visibilityState === "visible") void load(view.tab, view.sort, query);
    };
    document.addEventListener("visibilitychange", again);
    return () => document.removeEventListener("visibilitychange", again);
  }, [load, view.tab, view.sort, query]);

  async function remind(row: DeskRow) {
    if (!row.set_id) return;
    setFailed(null);
    const res = await fetch(`/api/question-sets/${encodeURIComponent(row.set_id)}/remind`, {
      method: "POST",
    });
    if (res.ok) setReminded((s) => new Set(s).add(row.idea_id));
    else setFailed(row.idea_id);
  }

  const decided = data.tab === "decided";
  const tabs = TABS.map((t) => ({ ...t, count: data.counts[t.value] }));
  const empty = EMPTY[data.tab];

  return (
    <div className="rd arrive">
      <header className="rd-head">
        <h1 className="h1">Review desk</h1>
        <p className="body rd-summary" role="status">
          {data.summary}
        </p>
      </header>

      <SearchBar
        label="Search the desk"
        placeholder="Search ideas, sharers or IDEA numbers, or ask: which ones are overdue?"
        text={text}
        onText={setText}
        filters={[]}
        picked={[]}
        onPicked={() => undefined}
        onSubmit={(q) => {
          setQuery(q.trim());
          void load(view.tab, view.sort, q.trim());
        }}
      />

      <div className="rd-bar">
        <Tabs
          id="desk"
          label="Review desk"
          tabs={tabs}
          value={view.tab}
          onChange={(t) => void load(t as DeskTab, view.sort, query)}
        />
        <Sorts
          options={SORT_OPTIONS}
          value={view.sort}
          onChange={(s) => void load(view.tab, s as DeskSort, query)}
        />
      </div>

      <section {...tabPanelProps("desk", view.tab)} className="rd-panel">
        {data.items.length === 0 ? (
          <Empty title={empty.title} align="left" level={2}>
            {empty.line}
          </Empty>
        ) : (
          <table className="rd-table">
            <thead>
              <tr>
                <th scope="col">Idea</th>
                <th scope="col">Questions</th>
                {decided ? (
                  <>
                    <th scope="col">Decision</th>
                    <th scope="col">Ones Committee</th>
                    <th scope="col">
                      <span className="vh">Action</span>
                    </th>
                  </>
                ) : (
                  <>
                    <th scope="col">Time left</th>
                    <th scope="col">Decide by</th>
                    <th scope="col">
                      <span className="vh">Action</span>
                    </th>
                  </>
                )}
              </tr>
            </thead>
            <tbody ref={body}>
              {data.items.map((row) => (
                <tr key={row.idea_id} data-flip={row.idea_id}>
                  <td className="rd-idea">
                    <Link href={`/desk/ideas/${encodeURIComponent(row.idea_id)}`} className="rd-title">
                      {row.title}
                    </Link>
                    <span className="meta">{row.who}</span>
                  </td>
                  <td className="rd-q">
                    <Dots asked={row.asked} answered={row.answered} />
                    <span className="meta">{row.questions}</span>
                  </td>
                  {decided ? (
                    <>
                      <td className="rd-decision">{row.decision}</td>
                      <td className="meta rd-committee">{row.committee}</td>
                      <td className="rd-act">
                        {/* Desk.md, Decided this week: "Open: {title}" on every row */}
                        <ButtonLink
                          variant="line"
                          size="sm"
                          href={`/desk/ideas/${encodeURIComponent(row.idea_id)}`}
                          aria-label={`Open: ${row.title}`}
                        >
                          Open
                        </ButtonLink>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="rd-time">
                        <TimeLeft row={row} tab={data.tab} now={now} />
                      </td>
                      <td className="rd-by">{row.decide_by}</td>
                      <td className="rd-act">
                        {row.action_kind === "remind" ? (
                          <>
                            {/* S-R1.rules/3, NOT DRAWN: "Reminded, just now" for the session; the name follows the
                                words on the button (WCAG 2.5.3). */}
                            <Button
                              variant="line"
                              size="sm"
                              disabled={reminded.has(row.idea_id)}
                              aria-label={`${reminded.has(row.idea_id) ? REMINDED : row.action}: ${row.title}`}
                              onClick={() => void remind(row)}
                            >
                              {reminded.has(row.idea_id) ? REMINDED : row.action}
                            </Button>
                            {failed === row.idea_id ? (
                              <span className="fmsg" role="alert">
                                The reminder didn’t go. Try again.
                              </span>
                            ) : null}
                          </>
                        ) : (
                          <ButtonLink
                            variant="line"
                            size="sm"
                            href={`/desk/ideas/${encodeURIComponent(row.idea_id)}`}
                            aria-label={`${row.action}: ${row.title}`}
                          >
                            {row.action}
                          </ButtonLink>
                        )}
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
