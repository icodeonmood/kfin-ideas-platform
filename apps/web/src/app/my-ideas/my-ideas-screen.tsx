"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type MouseEvent } from "react";

import { restoreRow, rowOffset } from "@/components/browse/return-to";
import { Status } from "@/components/status";
import { Button, ButtonLink } from "@/components/ui/button";
import { ChoiceChips } from "@/components/ui/chips";
import { Empty } from "@/components/ui/empty";
import { Pill } from "@/components/ui/pill";
import { SearchBar } from "@/components/ui/search";
import { SkeletonRows } from "@/components/ui/skeleton";
import { Sorts } from "@/components/ui/sorts";
import { Tabs, tabPanelProps } from "@/components/ui/tabs";
import type { MyIdeaRow, MyIdeasEmpty, MyIdeasResponse } from "@/lib/contracts/api";
import type { MyIdeasFilter, MyIdeasList, MyIdeasSort } from "@/lib/contracts/enums";
import { flip } from "@/lib/motion/flip";
import {
  cleanAddress,
  listOf,
  readSearch,
  replaceAddress,
  replaceAddressBeforeLeaving,
  SEARCH_MAX,
  writeSearch,
  type SearchList,
} from "@/lib/search-memory";

import "@/components/browse/browse.css";

type ListState = { list: MyIdeasList; filter: MyIdeasFilter; sort: MyIdeasSort; q: string };
/** The view an address with nothing in it names. */
const START: ListState = { list: "yours", filter: "all", sort: "latest", q: "" };
/** Where this tab keeps My ideas' search (DEC-110). */
const LIST: SearchList = "/my-ideas";

/** My ideas' own address for a list state, in the server's canonical order with defaults left out (A-API.my-ideas):
 * list, filter, sort, then the row to come back to and how far it sat from the top of the window. The search is
 * never in it: it stays in this tab's memory of the history entry (DEC-110, `lib/search-memory`). */
export function myIdeasHref(s: Omit<ListState, "q">, row?: string, dy?: number): string {
  const q = new URLSearchParams();
  if (s.list !== "yours") q.set("list", s.list);
  if (s.filter !== "all") q.set("filter", s.filter);
  if (s.sort !== "latest") q.set("sort", s.sort);
  if (row) q.set("row", row);
  if (row && dy !== undefined) q.set("dy", String(dy));
  const qs = q.toString();
  return qs ? `/my-ideas?${qs}` : "/my-ideas";
}

/** A search spaced as the server keeps it (ideapage/mine.py normalise). */
const spaced = (q: string) => q.split(/\s+/).filter(Boolean).join(" ").slice(0, SEARCH_MAX);

/** The view a state names, with the search spaced as the server keeps it, so a change the person asked for can be
 * matched with the server's answer for it. */
function viewKey(s: ListState): string {
  return `${myIdeasHref(s)}\n${spaced(s.q)}`;
}

/** The tab, filter and sort an address names; the search is the one given (an address never holds one). */
function stateFromHref(href: string, base: ListState, q = base.q): ListState {
  const p = new URL(href, "http://x").searchParams;
  return {
    list: (p.get("list") as MyIdeasList | null) ?? "yours",
    filter: (p.get("filter") as MyIdeasFilter | null) ?? "all",
    sort: (p.get("sort") as MyIdeasSort | null) ?? base.sort,
    q,
  };
}

/** The view the page's own address names, with the search this tab keeps for it. */
function addressView(q: string): ListState {
  return stateFromHref(window.location.pathname + window.location.search, START, q);
}

const LOAD_FAILED = "We can't load your ideas just now. Please try again in a minute.";
/** MyIdeas.md, `search=Suggestions open`: the example questions and what search reads. */
const ASKS = [
  "Which of my ideas need me this week?",
  "Ideas about the rejection SMS",
  "What did the review desk say no to, and why?",
];
const SEARCH_READS =
  "Search reads your titles, your own words, your files and the review desk’s notes, so it finds ideas by meaning, not only exact words.";

function MiniTrack({ track }: { track: NonNullable<MyIdeaRow["track"]> }) {
  return (
    <span className="mi-trk">
      <span className="mi-segs" aria-hidden="true">
        {track.segments.map((s, i) => (
          <i key={i} className={`mi-seg ${s}`} />
        ))}
      </span>
      <span className="vh">{track.label}</span>
    </span>
  );
}

function Chevron() {
  return (
    <svg className="mi-chev" width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

/** A view of My ideas from the server (A-API.my-ideas). A POST, so the search goes in the body and never in a URL
 * (DEC-110); null when it could not be read. */
async function readView(next: ListState, row: string | null): Promise<MyIdeasResponse | null> {
  try {
    const res = await fetch("/api/me/ideas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        list: next.list,
        filter: next.filter,
        sort: next.sort,
        q: spaced(next.q),
        ...(row ? { row } : {}),
      }),
      cache: "no-store",
    });
    return res.ok ? ((await res.json()) as MyIdeasResponse) : null;
  } catch {
    return null;
  }
}

/**
 * S-07, My ideas. The server renders the view the address names, without a search (an address never holds one,
 * DEC-110). Every change on the screen asks the server for its view (`POST /api/me/ideas`) and replaces the address
 * with its tab, filter and sort; the search goes into this tab's memory of the history entry. On arrival (a reload,
 * Back from an idea, the router's cached page) the screen reads the address and that memory once, and asks for the
 * view they name when it is not the one rendered, the list held as loading meanwhile so the unsearched list never
 * stands in for it (P-ROUTES.state, S-07.return, J-BROWSE/1 and /3).
 *
 * Quick changes build on each other: each one starts from the last asked for, and only the answer to the latest is
 * shown, so an earlier answer never undoes a later change. What the person types is never wiped by an answer; the box
 * takes the words of a new search only when the search itself changed (S-07.state).
 */
export function MyIdeasScreen({ data }: { data: MyIdeasResponse | null }) {
  const router = useRouter();
  const root = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(data);
  const shownNow = useRef(shown);
  const [fading, setFading] = useState(false);
  const [text, setText] = useState(data?.state.q ?? "");
  const textNow = useRef(text);
  const [arrival, setArrival] = useState<{ desk: string; phone: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const [notRead, setNotRead] = useState(false);
  // A view with the search this entry keeps has not been read yet: the list on screen is the server's unsearched one,
  // so it stays held under the failed line, and the kept words stay kept for a reload (DEC-110). `landedNow` is true
  // once any view for the entry's own words is on screen
  const [stuck, setStuck] = useState(false);
  const landedNow = useRef(false);
  const settle = useRef<(() => void) | null>(null);

  // What the person asked for last, ahead of the server's answer, so quick changes build on each other; the number
  // of the latest request, so only its answer lands; and the search the view on screen or asked for was read with
  const want = useRef<ListState | null>(null);
  const [wanted, setWanted] = useState<ListState | null>(null);
  const asks = useRef(0);
  const words = useRef("");
  const live = useRef(true);
  // Set while the router reads this page again after an action, so the search on screen is kept through it
  const refreshing = useRef(false);
  // Set once a row is opened: the list is left as it stands, so nothing that lands meanwhile (an answer, the router's
  // read of the address with the row in it) changes it or takes the row out of the address Back returns to
  const leaving = useRef(false);

  useEffect(() => {
    textNow.current = text;
  }, [text]);
  useEffect(() => {
    shownNow.current = shown;
  }, [shown]);
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);

  /** Asks the server for a view and shows its answer if no later change, Back or link has taken over meanwhile.
   * A view that could not be read leaves the list on screen as it is: the tabs, the sort, the address and the
   * search memory go back to it, the words in the box stay, and one line says so. */
  const ask = useCallback(
    async (next: ListState, how: "sort" | "fade" | "quiet", row: string | null = null) => {
      const n = ++asks.current;
      want.current = next;
      setWanted(next);
      if (how === "fade") setFading(true);
      const answer = await readView(next, row);
      if (n !== asks.current || !live.current || leaving.current) return;
      want.current = null;
      setWanted(null);
      setFading(false);
      if (answer) {
        setNotRead(false);
        setStuck(false);
        landedNow.current = true;
        setShown(answer);
        return;
      }
      settle.current?.();
      settle.current = null;
      setNotRead(true);
      // A failed read never wipes the kept words, and never leaves unsearched rows under them
      if (!landedNow.current && spaced(next.q)) {
        setStuck(true);
        return;
      }
      const was = shownNow.current;
      if (was) {
        words.current = spaced(was.state.q);
        writeSearch(LIST, words.current);
        replaceAddress(myIdeasHref(was.state));
      }
    },
    [],
  );

  /** The address and this tab's memory name a view: show the server's render when it is that view, else ask for it.
   * `first` is the page's arrival, when the list is held as loading until the answer lands. */
  const arrive = useCallback(
    (base: MyIdeasResponse, first: boolean) => {
      if (leaving.current) return;
      const refresh = refreshing.current;
      const kept = spaced(refresh ? words.current : readSearch(LIST));
      refreshing.current = false;
      // The router writes the entry's state afresh on its own navigations: the words go back in
      writeSearch(LIST, kept);
      if (kept !== words.current) {
        textNow.current = kept;
        setText(kept);
      }
      words.current = kept;
      const target = addressView(kept);
      if (!kept && viewKey(target) === viewKey({ ...base.state, q: "" })) {
        asks.current += 1; // a change still on its way gives way to the view the address now names
        want.current = null;
        setWanted(null);
        setFading(false);
        setStuck(false);
        landedNow.current = true;
        setShown(base);
        return;
      }
      if (want.current && viewKey(want.current) === viewKey(target)) return; // already on its way
      // The router also reads the page again when the address moves; with a search, the view on screen already is the
      // one it names, unless an action changed what is in it
      const on = shownNow.current;
      if (!first && !refresh && on && viewKey({ ...on.state, q: spaced(on.state.q) }) === viewKey(target))
        return;
      const row = new URL(window.location.href).searchParams.get("row");
      void ask(target, first ? "fade" : "quiet", row);
    },
    [ask],
  );

  // Each render from the server (arrival, Back, a link, a refresh) is read against the address and the search memory
  const seen = useRef<MyIdeasResponse | null | undefined>(undefined);
  useLayoutEffect(() => {
    if (seen.current === data) return;
    const first = seen.current === undefined;
    seen.current = data;
    if (first) cleanAddress();
    if (data) arrive(data, first);
  }, [data, arrive]);

  // Back or Forward moved the address before an answer came: the change in flight gives way, and the screen reads
  // the entry it is now on (P-ROUTES.state). An answer to the person's own change is left alone.
  useEffect(() => {
    const moved = () => {
      leaving.current = false;
      asks.current += 1;
      want.current = null;
      setWanted(null);
      setFading(false);
      window.setTimeout(() => {
        const base = shownNow.current;
        if (live.current && base && listOf(window.location.pathname) === LIST) arrive(base, false);
      }, 0);
    };
    window.addEventListener("popstate", moved);
    return () => window.removeEventListener("popstate", moved);
  }, [arrive]);

  // A sort's new order has rendered: the glide can measure where each row went
  useLayoutEffect(() => {
    settle.current?.();
    settle.current = null;
  }, [shown]);

  // Back from an idea (S-07.return, J-BROWSE/3): the row is where it was, focused and washed once, and a quiet
  // line says so. The line shows first and the row is placed after it has rendered, so the line never pushes the row
  // away from where it sat. The row and its offset leave the address once used, so it reads as the list's own again.
  // Not before the view with the search this entry keeps is on screen, or the row would be placed in another list.
  const [restore, setRestore] = useState<{ row: string; dy: number | null } | null>(null);
  useEffect(() => {
    if (!shown || want.current || leaving.current || spaced(shown.state.q) !== spaced(readSearch(LIST)))
      return;
    const url = new URL(window.location.href);
    const row = url.searchParams.get("row");
    if (!row) return;
    const dyRaw = url.searchParams.get("dy");
    const frame = requestAnimationFrame(() => {
      if (leaving.current) return;
      if (root.current?.querySelector(`[data-row="${CSS.escape(row)}"]`)) {
        const tab = shown.tabs.find((t) => t.selected)?.label ?? "Yours";
        const filter = shown.filters.find((f) => f.selected)?.short_label ?? "All";
        const sort = shown.sorts.find((s) => s.selected)?.label.toLowerCase() ?? "latest activity";
        setArrival({
          desk: shown.arrival?.line ?? `Back where you were: ${tab}.`,
          phone: `Back where you were: ${filter}, ${sort} first.`,
        });
        setRestore({ row, dy: dyRaw ? Number(dyRaw) : null });
      }
      url.searchParams.delete("row");
      url.searchParams.delete("dy");
      replaceAddress(url.pathname + url.search);
    });
    return () => cancelAnimationFrame(frame);
  }, [shown]);
  const restored = useRef<object | null>(null);
  useLayoutEffect(() => {
    if (!restore || restored.current === restore) return;
    restored.current = restore;
    restoreRow(root.current, restore.row, restore.dy);
  }, [restore]);

  if (!shown) {
    return (
      <div className="mi">
        <Head />
        <Status kind="error" title={LOAD_FAILED} className="mi-fail" />
      </div>
    );
  }

  const cur = (): ListState => want.current ?? { ...shown.state, q: words.current };
  const rows = () => root.current?.querySelectorAll<HTMLElement>(".mi-list [data-flip]") ?? [];

  /** Every change replaces the address with its tab, filter and sort, keeps its search in this tab's memory, and the
   * server answers with that view (P-ROUTES.state, DEC-110). A sort glides the rows to their new order; a tab, filter
   * or search fades the list through, with three skeleton rows meanwhile. */
  const go = (patch: Partial<ListState>, how: "sort" | "fade" = "fade") => {
    const now = cur();
    const next = { ...now, ...patch };
    // A new search from here (Enter, an example question, Clear, a link on the screen) puts its words in the box at
    // once, so its answer can leave the box to whatever the person types next
    if (spaced(next.q) !== spaced(now.q)) {
      textNow.current = next.q;
      setText(next.q);
    }
    setArrival(null);
    setNotRead(false);
    setStuck(false);
    words.current = spaced(next.q);
    writeSearch(LIST, words.current);
    replaceAddress(myIdeasHref(next));
    if (how === "sort") {
      void flip(
        rows,
        () =>
          new Promise<void>((resolve) => {
            settle.current = resolve;
            window.setTimeout(resolve, 4_000);
            void ask(next, "sort");
          }),
      );
      return;
    }
    void ask(next, "fade");
  };

  const open = (e: MouseEvent<HTMLAnchorElement>, row: MyIdeaRow, to: string) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    leaving.current = true;
    replaceAddressBeforeLeaving(myIdeasHref(cur(), row.id, rowOffset(e.currentTarget)));
    router.push(to);
  };

  const postAction = async (row: MyIdeaRow) => {
    const a = row.next_step.action;
    if (!a.path) return;
    setFailed(null);
    try {
      const res = await fetch(a.path, { method: "POST", headers: { "Content-Type": "application/json" } });
      if (!res.ok) throw new Error(String(res.status));
      refreshing.current = true;
      router.refresh();
    } catch {
      setFailed(row.id);
    }
  };

  // An action only the desktop board draws ("See 1 in Teamed up") is not shown on a phone, whose empty states
  // offer "Show all ideas" alone (PhoneMyIdeas.md)
  const emptyAction = (a: MyIdeasEmpty["actions"][number], i: number) =>
    a.to.startsWith("/my-ideas") ? (
      <Button
        key={a.label}
        variant={a.style === "primary" ? "primary" : "line"}
        className={a.desk_only ? "mi-desk" : undefined}
        // The search's own empty state clears it ("Clear"); any other keeps it (DEC-110: no link names a search)
        onClick={() => go(stateFromHref(a.to, cur(), shown.empty?.kind === "no_results" ? "" : cur().q))}
      >
        {a.label}
      </Button>
    ) : (
      <ButtonLink
        key={a.label}
        href={a.to}
        variant={a.style === "line" || (i > 0 && !a.style) ? "line" : "primary"}
        className={a.desk_only ? "mi-desk" : undefined}
      >
        {a.label}
      </ButtonLink>
    );

  if (shown.empty?.kind === "first_time") {
    const e = shown.empty;
    return (
      <div className="mi" ref={root}>
        <Head />
        <div className="card mi-first">
          <Empty
            title={e.title}
            level={2}
            action={
              <>
                {e.hint ? <span className="mi-hint mi-desk">{e.hint}</span> : null}
                {e.actions.map((a) => (
                  <ButtonLink key={a.label} href={a.to}>
                    {a.label}
                  </ButtonLink>
                ))}
              </>
            }
          >
            <span className="mi-desk">{e.line}</span>
            <span className="mi-phone">
              Spot something that keeps going wrong? Say it in your own words, typed or spoken. It takes about
              two minutes.
            </span>
          </Empty>
        </div>
      </div>
    );
  }

  const loading = fading;
  // Counts are left out while a list loads, and while the kept search could not be read
  const hide = loading || stuck;
  const state = wanted ?? shown.state;
  const list = loading ? state.list : shown.state.list;
  const picked = state.filter !== "all" ? [state.filter] : [];

  return (
    <div className="mi" ref={root}>
      <Head />
      <div id="find" className={state.q || stuck ? "mi-search" : "mi-search mi-desk"}>
        <SearchBar
          label="Search your ideas, or ask a question"
          placeholder="Search your ideas"
          text={text}
          onText={(t) => {
            textNow.current = t;
            setText(t);
          }}
          filters={shown.filters
            .filter((f) => f.filter !== "all")
            .map((f) => ({ value: f.filter, label: f.label, count: f.count }))}
          picked={picked}
          onPicked={(p) => {
            const filter = (p.length ? p[p.length - 1] : "all") as MyIdeasFilter;
            // Clear empties the box first: then the search goes too
            go(textNow.current === "" ? { filter, q: "" } : { filter });
          }}
          onSubmit={(t) => go({ q: t.trim() })}
          // The panel's "Or ask in your own words", its three example questions and the line on what search reads,
          // as MyIdeas.md's "Suggestions open" state draws them (C-SEARCH.behaviour/1). A question goes in `q`
          // like any search.
          // TODO(lane F): answering a question in your own words ("Read your question as “Needs you”…",
          // L-SEARCH/4-5) is lane F's search on the same `q`; until it lands the words are matched as text.
          asks={ASKS}
          onAsk={(question) => {
            textNow.current = question;
            go({ q: question });
          }}
          foot={SEARCH_READS}
          answer={
            shown.search && !loading
              ? { line: shown.search.sentence, source: shown.search.matched_line }
              : undefined
          }
        />
      </div>

      <div className="mi-bar">
        <Tabs
          id="mi"
          label="Your ideas"
          tabs={shown.tabs.map((t) => ({
            value: t.list,
            label: t.label,
            count: hide ? undefined : t.count,
          }))}
          value={list}
          onChange={(v) => go({ list: v as MyIdeasList })}
        />
        <div className="mi-desk">
          <Sorts
            options={shown.sorts.map((s) => ({ value: s.sort, label: s.label }))}
            value={state.sort}
            onChange={(v) => go({ sort: v as MyIdeasSort }, "sort")}
          />
        </div>
      </div>

      <div className="mi-phone mi-pchips">
        <ChoiceChips
          label="Filter"
          scroll
          filter
          options={shown.filters.map((f) => ({
            value: f.filter,
            label: f.short_label,
            count: hide ? undefined : f.count,
          }))}
          value={state.filter}
          onChange={(v) => go({ filter: v as MyIdeasFilter })}
        />
        <div className="mi-ptools">
          {/* On a phone C-SORTS shows itself as one cycler, "Sorted by latest activity" (S-07.phone) */}
          <Sorts
            options={shown.sorts.map((s) => ({ value: s.sort, label: s.label }))}
            value={state.sort}
            onChange={(v) => go({ sort: v as MyIdeasSort }, "sort")}
          />
          <Button
            variant="text"
            onClick={() => {
              void navigator.clipboard
                ?.writeText(new URL(shown.copy_link.url, window.location.origin).href)
                .then(() => {
                  setCopied(true);
                  window.setTimeout(() => setCopied(false), 2_500);
                })
                .catch(() => undefined);
            }}
          >
            {copied ? shown.copy_link.done : shown.copy_link.label}
          </Button>
        </div>
      </div>

      <p className="mi-back mi-desk" role="status">
        {arrival?.desk ?? ""}
      </p>
      <p className="mi-back mi-phone" role="status">
        {arrival?.phone ?? ""}
      </p>

      {notRead ? <Status kind="error" title={LOAD_FAILED} className="mi-fail" /> : null}

      <div {...tabPanelProps("mi", list)} className="mi-panel">
        {loading ? (
          <SkeletonRows what="Loading your ideas" />
        ) : stuck ? null : shown.empty ? (
          <div className="card mi-emptyc">
            <Empty title={shown.empty.title} action={<>{shown.empty.actions.map(emptyAction)}</>}>
              {shown.empty.phone_line ? (
                <>
                  <span className="mi-desk">{shown.empty.line}</span>
                  <span className="mi-phone">{shown.empty.phone_line}</span>
                </>
              ) : (
                shown.empty.line
              )}
            </Empty>
          </div>
        ) : (
          <>
            <div className="mi-row mi-hd mi-desk" aria-hidden="true">
              <p>Idea</p>
              <p>Where it is</p>
              <p>Next step</p>
            </div>
            <ul className="mi-list" aria-label={shown.tabs.find((t) => t.selected)?.label ?? "Your ideas"}>
              {shown.items.map((r) => {
                const a = r.next_step.action;
                return (
                  <li key={r.id} className="mi-row" data-row={r.id} data-flip={r.id} data-handover="expand">
                    <div className="mi-idea">
                      <h3 className="mi-t">
                        <Link href={r.href} onClick={(e) => open(e, r, r.href)}>
                          {r.title}
                        </Link>
                      </h3>
                      <p className="mi-meta">{r.meta}</p>
                      {r.snippet ? <p className="mi-snip">{r.snippet}</p> : null}
                    </div>
                    <div className="mi-where">
                      <Pill variant={r.pill.variant}>{r.pill.label}</Pill>
                      {r.track ? <MiniTrack track={r.track} /> : null}
                    </div>
                    <div className="mi-next">
                      {r.next_step.phone_sentence ? (
                        <p className="mi-ns">
                          <span className="mi-desk">{r.next_step.sentence}</span>
                          <span className="mi-phone">{r.next_step.phone_sentence}</span>
                        </p>
                      ) : (
                        <p className="mi-ns">{r.next_step.sentence}</p>
                      )}
                      {a.to ? (
                        <ButtonLink
                          href={a.to}
                          variant={a.style === "primary" ? "primary" : "line"}
                          className="mi-act"
                          aria-label={a.accessible_name}
                          onClick={(e) => open(e, r, a.to!)}
                        >
                          {a.label}
                          <Chevron />
                        </ButtonLink>
                      ) : a.path ? (
                        <Button
                          variant={a.style === "primary" ? "primary" : "line"}
                          className="mi-act"
                          aria-label={a.accessible_name}
                          onClick={() => void postAction(r)}
                        >
                          {a.label}
                        </Button>
                      ) : null}
                      {failed === r.id ? (
                        <Status
                          kind="error"
                          title="We can't do that just now. Please try again in a minute."
                        />
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}

function Head() {
  return (
    <header className="mi-head">
      <h1 className="h1 mi-title">My ideas</h1>
      <p className="mi-lead mi-desk">
        Everything you’ve shared or teamed up on, where it is and what happens next.
      </p>
    </header>
  );
}
