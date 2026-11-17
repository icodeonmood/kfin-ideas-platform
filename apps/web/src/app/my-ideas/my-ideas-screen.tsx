"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useLayoutEffect, useRef, useState, useTransition, type MouseEvent } from "react";

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

import "@/components/browse/browse.css";

type ListState = { list: MyIdeasList; filter: MyIdeasFilter; sort: MyIdeasSort; q: string };

/** My ideas' own address for a list state, in the server's canonical order with defaults left out (A-API.my-ideas):
 * list, filter, sort, q, then the row to come back to and how far it sat from the top of the window. */
export function myIdeasHref(s: ListState, row?: string, dy?: number): string {
  const q = new URLSearchParams();
  if (s.list !== "yours") q.set("list", s.list);
  if (s.filter !== "all") q.set("filter", s.filter);
  if (s.sort !== "latest") q.set("sort", s.sort);
  if (s.q) q.set("q", s.q);
  if (row) q.set("row", row);
  if (row && dy !== undefined) q.set("dy", String(dy));
  const qs = q.toString();
  return qs ? `/my-ideas?${qs}` : "/my-ideas";
}

function stateFromHref(href: string, base: ListState): ListState {
  const p = new URL(href, "http://x").searchParams;
  return {
    list: (p.get("list") as MyIdeasList | null) ?? "yours",
    filter: (p.get("filter") as MyIdeasFilter | null) ?? "all",
    sort: (p.get("sort") as MyIdeasSort | null) ?? base.sort,
    q: p.get("q") ?? "",
  };
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

export function MyIdeasScreen({ data }: { data: MyIdeasResponse | null }) {
  const router = useRouter();
  const root = useRef<HTMLDivElement>(null);
  const [pending, startTransition] = useTransition();
  const [fading, setFading] = useState(false);
  const [text, setText] = useState(data?.state.q ?? "");
  const textNow = useRef(text);
  const [arrival, setArrival] = useState<{ desk: string; phone: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const settle = useRef<(() => void) | null>(null);

  // What the person asked for last, ahead of the server's answer, so quick changes build on each other
  const want = useRef<ListState | null>(null);
  const [wanted, setWanted] = useState<ListState | null>(null);
  const [given, setGiven] = useState(data);
  if (given !== data) {
    setGiven(data);
    setText(data?.state.q ?? "");
    setFading(false);
    setWanted(null);
  }
  useEffect(() => {
    textNow.current = data?.state.q ?? "";
    want.current = null;
  }, [data]);

  // A sort's new order has rendered: the glide can measure where each row went
  useLayoutEffect(() => {
    settle.current?.();
    settle.current = null;
  }, [data]);

  // Back from an idea (S-07.return, J-BROWSE/3): the row is where it was, focused and washed once, and a quiet
  // line says so. The line shows first and the row is placed after it has rendered, so the line never pushes the row
  // away from where it sat. The row and its offset leave the address once used, so it reads as the list's own again.
  const [restore, setRestore] = useState<{ row: string; dy: number | null } | null>(null);
  useEffect(() => {
    if (!data) return;
    const url = new URL(window.location.href);
    const row = url.searchParams.get("row");
    if (!row) return;
    const dyRaw = url.searchParams.get("dy");
    const frame = requestAnimationFrame(() => {
      if (root.current?.querySelector(`[data-row="${CSS.escape(row)}"]`)) {
        const tab = data.tabs.find((t) => t.selected)?.label ?? "Yours";
        const filter = data.filters.find((f) => f.selected)?.short_label ?? "All";
        const sort = data.sorts.find((s) => s.selected)?.label.toLowerCase() ?? "latest activity";
        setArrival({
          desk: data.arrival?.line ?? `Back where you were: ${tab}.`,
          phone: `Back where you were: ${filter}, ${sort} first.`,
        });
        setRestore({ row, dy: dyRaw ? Number(dyRaw) : null });
      }
      url.searchParams.delete("row");
      url.searchParams.delete("dy");
      window.history.replaceState(window.history.state, "", url.pathname + url.search);
    });
    return () => cancelAnimationFrame(frame);
  }, [data]);
  const restored = useRef<object | null>(null);
  useLayoutEffect(() => {
    if (!restore || restored.current === restore) return;
    restored.current = restore;
    restoreRow(root.current, restore.row, restore.dy);
  }, [restore]);

  if (!data) {
    return (
      <div className="mi">
        <Head />
        <Status kind="error" title={LOAD_FAILED} className="mi-fail" />
      </div>
    );
  }

  const cur = (): ListState => want.current ?? { ...data.state };
  const rows = () => root.current?.querySelectorAll<HTMLElement>(".mi-list [data-flip]") ?? [];

  /** Every change replaces the address and the server answers with that view (P-ROUTES.state). A sort glides the
   * rows to their new order; a tab, filter or search fades the list through, with three skeleton rows meanwhile. */
  const go = (patch: Partial<ListState>, how: "sort" | "fade" = "fade") => {
    const next = { ...cur(), ...patch };
    want.current = next;
    setWanted(next);
    setArrival(null);
    const url = myIdeasHref(next);
    if (how === "sort") {
      void flip(
        rows,
        () =>
          new Promise<void>((resolve) => {
            settle.current = resolve;
            window.setTimeout(resolve, 4_000);
            startTransition(() => router.replace(url, { scroll: false }));
          }),
      );
      return;
    }
    setFading(true);
    startTransition(() => router.replace(url, { scroll: false }));
  };

  const open = (e: MouseEvent<HTMLAnchorElement>, row: MyIdeaRow, to: string) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    window.history.replaceState(null, "", myIdeasHref(cur(), row.id, rowOffset(e.currentTarget)));
    router.push(to);
  };

  const postAction = async (row: MyIdeaRow) => {
    const a = row.next_step.action;
    if (!a.path) return;
    setFailed(null);
    try {
      const res = await fetch(a.path, { method: "POST", headers: { "Content-Type": "application/json" } });
      if (!res.ok) throw new Error(String(res.status));
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
        onClick={() => go(stateFromHref(a.to, cur()))}
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

  if (data.empty?.kind === "first_time") {
    const e = data.empty;
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

  const loading = pending && fading;
  const state = wanted ?? data.state;
  const list = loading ? state.list : data.state.list;
  const picked = state.filter !== "all" ? [state.filter] : [];

  return (
    <div className="mi" ref={root}>
      <Head />
      <div id="find" className={state.q ? "mi-search" : "mi-search mi-desk"}>
        <SearchBar
          label="Search your ideas, or ask a question"
          placeholder="Search your ideas"
          text={text}
          onText={(t) => {
            textNow.current = t;
            setText(t);
          }}
          filters={data.filters
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
            data.search && !loading
              ? { line: data.search.sentence, source: data.search.matched_line }
              : undefined
          }
        />
      </div>

      <div className="mi-bar">
        <Tabs
          id="mi"
          label="Your ideas"
          tabs={data.tabs.map((t) => ({
            value: t.list,
            label: t.label,
            count: loading ? undefined : t.count,
          }))}
          value={list}
          onChange={(v) => go({ list: v as MyIdeasList })}
        />
        <div className="mi-desk">
          <Sorts
            options={data.sorts.map((s) => ({ value: s.sort, label: s.label }))}
            value={state.sort}
            onChange={(v) => go({ sort: v as MyIdeasSort }, "sort")}
          />
        </div>
      </div>

      <div className="mi-phone mi-pchips">
        <ChoiceChips
          label="Filter"
          scroll
          options={data.filters.map((f) => ({
            value: f.filter,
            label: f.short_label,
            count: loading ? undefined : f.count,
          }))}
          value={state.filter}
          onChange={(v) => go({ filter: v as MyIdeasFilter })}
        />
        <div className="mi-ptools">
          {/* On a phone C-SORTS shows itself as one cycler, "Sorted by latest activity" (S-07.phone) */}
          <Sorts
            options={data.sorts.map((s) => ({ value: s.sort, label: s.label }))}
            value={state.sort}
            onChange={(v) => go({ sort: v as MyIdeasSort }, "sort")}
          />
          <Button
            variant="text"
            onClick={() => {
              void navigator.clipboard
                ?.writeText(new URL(data.copy_link.url, window.location.origin).href)
                .then(() => {
                  setCopied(true);
                  window.setTimeout(() => setCopied(false), 2_500);
                })
                .catch(() => undefined);
            }}
          >
            {copied ? data.copy_link.done : data.copy_link.label}
          </Button>
        </div>
      </div>

      <p className="mi-back mi-desk" role="status">
        {arrival?.desk ?? ""}
      </p>
      <p className="mi-back mi-phone" role="status">
        {arrival?.phone ?? ""}
      </p>

      <div {...tabPanelProps("mi", list)} className="mi-panel">
        {loading ? (
          <SkeletonRows what="Loading your ideas" />
        ) : data.empty ? (
          <div className="card mi-emptyc">
            <Empty title={data.empty.title} action={<>{data.empty.actions.map(emptyAction)}</>}>
              {data.empty.phone_line ? (
                <>
                  <span className="mi-desk">{data.empty.line}</span>
                  <span className="mi-phone">{data.empty.phone_line}</span>
                </>
              ) : (
                data.empty.line
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
            <ul className="mi-list" aria-label={data.tabs.find((t) => t.selected)?.label ?? "Your ideas"}>
              {data.items.map((r) => {
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
