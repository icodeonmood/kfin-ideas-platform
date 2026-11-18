"use client";

/**
 * S-R1 Review desk (L-REVIEW.queue): search, four tabs with counts, a sort, and one table whose rows carry every
 * running clock. Countdowns tick each minute without a reload (S-R1.rules/2); tab, sort and search are kept in the
 * URL, and Back returns to the row that was opened (S-R1.rules/4); "Remind {sharer}" acts in place (S-R1.rules/3).
 * On a phone the table becomes cards (S-R1.rules/6).
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type MouseEvent } from "react";

import { restoreRow, rowOffset } from "@/components/browse/return-to";
import { Button, ButtonLink } from "@/components/ui/button";
import { Empty } from "@/components/ui/empty";
import { Pill, type PillVariant } from "@/components/ui/pill";
import { SearchBar } from "@/components/ui/search";
import { Sorts } from "@/components/ui/sorts";
import { Tabs, tabPanelProps } from "@/components/ui/tabs";
import type { CountdownVariant, DeskResponse, DeskRow, DeskSort, DeskTab } from "@/lib/contracts";
import { addressBack, deskHref, deskUrlState, type DeskList } from "@/lib/desk/address";
import { countdown, countdownLabel, nextTickMs } from "@/lib/desk/countdown";
import { useFlipList } from "@/lib/motion/flip";

import "@/components/browse/browse.css";

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

/** How a list read ended: on screen, not read (the old list stays), or overtaken by a newer read. */
type Loaded = "shown" | "failed" | "superseded";

const ideaHref = (row: DeskRow) => `/desk/ideas/${encodeURIComponent(row.idea_id)}`;

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
    <Pill variant={PILL[variant]} countdown>
      {label}
    </Pill>
  );
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
  const router = useRouter();
  const body = useRef<HTMLTableSectionElement>(null);
  // The read in flight, or null once it has settled
  const loading = useRef<AbortController | null>(null);
  // False once the desk has gone (a row was opened): a read that settles later changes neither the page nor the address
  const live = useRef(true);
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
      loading.current?.abort();
    };
  }, []);
  // The tab, sort and search of the list on screen, kept with every list that lands
  const shown = useRef<DeskList>({ tab: initial.tab, sort: initial.sort, q: initialQuery });
  useFlipList(body, `${data.tab}:${data.sort}:${data.items.map((r) => r.idea_id).join(",")}`);

  /** Reads the list for a tab, sort and search. `write` is false only on arrival, when the address already names it.
   * Says whether that list is now on screen, or a newer request took over. */
  const load = useCallback(async (tab: DeskTab, sort: DeskSort, q: string, write = true): Promise<Loaded> => {
    const params = new URLSearchParams({ tab, sort });
    if (q) params.set("q", q);
    setView({ tab, sort });
    // The address takes the tab, sort and search at once, without a navigation: a router navigation waits for the
    // server, and a row opened before it lands would leave Back on the old address (S-R1.rules/4, J-BROWSE/4).
    if (write) window.history.replaceState(null, "", deskHref({ tab, sort, q }));
    loading.current?.abort();
    const ctl = new AbortController();
    loading.current = ctl;
    try {
      const res = await fetch(`/api/desk?${params.toString()}`, { signal: ctl.signal, cache: "no-store" });
      if (res.ok) {
        const next = (await res.json()) as DeskResponse;
        if (loading.current !== ctl || !live.current) return "superseded";
        loading.current = null;
        shown.current = { tab: next.tab, sort: next.sort, q };
        setData(next);
        return "shown";
      }
    } catch {
      // a newer request took over (it aborted this one), the desk has gone, or the network dropped
    }
    if (loading.current !== ctl || !live.current) return "superseded";
    loading.current = null;
    // Not read: the table keeps what it had, so the tabs, the sort, the search and the address go back to that list
    // rather than name a choice over rows it does not hold (S-R1.rules/4). The words in the search box stay.
    const was = shown.current;
    setView({ tab: was.tab, sort: was.sort });
    setQuery(was.q);
    const address = addressBack(was, { tab, sort, q });
    if (address) window.history.replaceState(null, "", address);
    return "failed";
  }, []);

  // Back to the desk: the router may restore the page from its cache, with the props it had when the person left and
  // for an older address. So the list is read once on arrival, as it is now (an idea decided meanwhile has left its
  // tab), for the tab, sort and search the address names (S-R1.rules/4, L-REVIEW.queue).
  // When the address also names the row that was opened (J-BROWSE/4), that row goes back to where it sat, its link has
  // focus and it is washed once, as on the Wall and My ideas; unless the person has moved focus meanwhile, or the
  // idea has left the list. The row and its offset leave the address at once, so it reads as the list's own again.
  const [back, setBack] = useState<{ row: string; dy: number | null } | null>(null);
  useEffect(() => {
    const want = deskUrlState(window.location.search);
    const before = loading.current;
    const focused = document.activeElement;
    const frame = requestAnimationFrame(() => {
      // The person chose a tab, sort or search before this frame: that list is already on its way
      if (loading.current !== before) return;
      setText(want.q);
      setQuery(want.q);
      if (want.row) {
        const url = new URL(window.location.href);
        url.searchParams.delete("row");
        url.searchParams.delete("dy");
        window.history.replaceState(null, "", url.pathname + url.search);
      }
      void load(want.tab ?? shown.current.tab, want.sort ?? shown.current.sort, want.q, false).then((got) => {
        const active = document.activeElement;
        const moved = active !== null && active !== document.body && active !== focused;
        if (want.row && got !== "superseded" && !moved) setBack({ row: want.row, dy: want.dy });
      });
    });
    return () => cancelAnimationFrame(frame);
  }, [load]);
  const restored = useRef<object | null>(null);
  useLayoutEffect(() => {
    if (!back || restored.current === back) return;
    restored.current = back;
    // A re-sort glide still running would move the row while it is measured: the list simply stands as it is now
    body.current?.querySelectorAll<HTMLElement>("[data-flip]").forEach((r) => {
      r.getAnimations().forEach((a) => a.finish());
    });
    restoreRow(body.current, back.row, back.dy);
  }, [back]);

  /** Opens an idea with the way back in the desk's address: this list, the row and how far it sat from the top of the
   * window (J-BROWSE/4). A link opened in a new tab or window is left to the browser. */
  const open = (e: MouseEvent<HTMLAnchorElement>, row: DeskRow) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    const list = { tab: view.tab, sort: view.sort, q: query };
    window.history.replaceState(null, "", deskHref(list, row.idea_id, rowOffset(e.currentTarget)));
    router.push(ideaHref(row));
  };

  // A reviewer coming back to the tab sees clocks and tabs as they are now (L-REVIEW.queue).
  useEffect(() => {
    const again = () => {
      // a read already on its way is as fresh, and replacing it would drop the row the arrival read restores
      if (document.visibilityState === "visible" && !loading.current) void load(view.tab, view.sort, query);
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
                <tr key={row.idea_id} data-flip={row.idea_id} data-row={row.idea_id}>
                  <td className="rd-idea">
                    <Link href={ideaHref(row)} className="rd-title" onClick={(e) => open(e, row)}>
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
                          href={ideaHref(row)}
                          aria-label={`Open: ${row.title}`}
                          onClick={(e) => open(e, row)}
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
                            href={ideaHref(row)}
                            aria-label={`${row.action}: ${row.title}`}
                            onClick={(e) => open(e, row)}
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
