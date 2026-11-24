// @vitest-environment jsdom
/**
 * BLD-A252 (J-BROWSE/4, S-R1.rules/4, S-07.return): a row opened on the review desk or My ideas writes the list's
 * address for Back (the row and how far it sat) with the App Router's own keys kept in the entry's state, then
 * pushes the idea. Next 16.4.5 patches `history.replaceState` (client/components/app-router.js:302-311): a state with
 * `__NA` passes straight through to the browser; one without has the keys copied back and the router restores that
 * address. A stand-in for the patch below records each restore, so the tests show that the click's only router
 * action is the push, while a sort or search right before it (a change in place) is still adopted with a restore.
 * The real `open()` handlers run, through the screens. Synthetic people and ideas.
 */
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DeskResponse, DeskRow } from "@/lib/contracts";
import { readSearch } from "@/lib/search-memory";

/** What the router did, in order: "restore <url>" from the patched replaceState, "push <url>" from router.push. */
const log = vi.hoisted(() => [] as string[]);
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: (url: string) => log.push(`push ${url}`), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(window.location.search),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));
vi.mock("@/lib/motion/flip", () => ({
  useFlipList: () => undefined,
  // A sort's glide is motion only: the change runs at once
  flip: (_rows: unknown, change: () => Promise<void>) => {
    void change();
    return Promise.resolve();
  },
}));

const { DeskView } = await import("@/app/desk/desk-view");
const { MyIdeasScreen } = await import("@/app/my-ideas/my-ideas-screen");
type MyData = NonNullable<Parameters<typeof MyIdeasScreen>[0]["data"]>;

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const TREE = { tree: ["", { children: ["__PAGE__", {}] }], renderedSearch: "" };
const WORDS = "Zebra7Kestrel";
/** Every state the page wrote to the entry, with its address, in order. */
let writes: { state: Record<string, unknown>; url: string }[] = [];

/** A stand-in for Next 16.4.5's patched `history.replaceState` (app-router.js:302-311, copy at :128-140). */
function patchLikeNext() {
  const browser = window.history.replaceState.bind(window.history);
  window.history.replaceState = function replaceState(
    data: unknown,
    unused: string,
    url?: string | URL | null,
  ) {
    const d = (data ?? {}) as Record<string, unknown>;
    writes.push({ state: { ...d }, url: String(url ?? "") });
    if (d.__NA || d._N) return browser(d, unused, url);
    const now = window.history.state as Record<string, unknown> | null;
    if (now?.__NA) d.__NA = now.__NA;
    if (now?.__PRIVATE_NEXTJS_INTERNALS_TREE)
      d.__PRIVATE_NEXTJS_INTERNALS_TREE = now.__PRIVATE_NEXTJS_INTERNALS_TREE;
    if (url) log.push(`restore ${String(url)}`);
    return browser(d, unused, url);
  };
}

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  log.length = 0;
  writes = [];
  // jsdom draws no layout and runs no animations
  (Element.prototype as unknown as { getAnimations: () => Animation[] }).getAnimations = () => [];
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
  Element.prototype.scrollIntoView = vi.fn();
  Element.prototype.getClientRects = (() => [new DOMRect(0, 0, 10, 10)]) as unknown as () => DOMRectList;
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
  delete (window.history as { replaceState?: unknown }).replaceState; // the browser's own again
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
});

/** The entry as the App Router leaves it after its own navigation: its keys in the state. */
function arriveAt(href: string) {
  window.history.replaceState({ __NA: true, __PRIVATE_NEXTJS_INTERNALS_TREE: TREE }, "", href);
  patchLikeNext();
}
async function settle() {
  for (let i = 0; i < 3; i++) {
    await act(async () => await new Promise<void>((r) => requestAnimationFrame(() => r())));
    for (let j = 0; j < 6; j++) await act(async () => await Promise.resolve());
  }
}
const here = () => window.location.pathname + window.location.search;
const click = (el: Element) =>
  act(() => {
    el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 }));
  });
function search(words: string) {
  const box = host.querySelector<HTMLInputElement>('input[type="search"]')!;
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  act(() => {
    set.call(box, words);
    box.dispatchEvent(new Event("input", { bubbles: true }));
  });
  act(() => {
    box.form!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  });
}
/** The click's own write: the last state written before the push. */
function leaving() {
  const last = writes.at(-1)!;
  return { state: last.state, url: last.url };
}
/** The server: the first `answered` list reads land with these bodies; every later read stays on its way, so a row
 * is clicked before the sort's or search's list lands, as in the flake. */
function serve(...answered: unknown[]) {
  let n = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(() => {
      const body = answered[n++];
      return body === undefined
        ? new Promise<Response>(() => undefined)
        : Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
    }),
  );
}

// --- S-R1, the review desk ------------------------------------------------------------------------------------

function deskRow(id: string, title: string): DeskRow {
  return {
    idea_id: id,
    title,
    who: "Kavya Menon, Investor service, Hyderabad",
    questions: "0 of 3 answered",
    time_left: "3 days to answer",
    variant: "normal",
    due_at: null,
    decide_by: "Friday 20 November",
    action: "Open",
    action_kind: "open",
    decision: null,
    committee: null,
    area: "Investor service",
    asked: 3,
    answered: 0,
    set_id: null,
  };
}
const ROWS = [
  deskRow("IDEA-2026-000501", "Rejection SMS gives a code"),
  deskRow("IDEA-2026-000502", `${WORDS} branch form`),
];
function desk(items: DeskRow[]): DeskResponse {
  return {
    items,
    total: items.length,
    counts: { to_review: 0, waiting: items.length, answered: 0, decided: 0 },
    summary: `${items.length} waiting on colleagues.`,
    tab: "waiting",
    sort: "time_left",
    waiting_on_sharers: [],
    now: "2026-11-18T10:00:00+05:30",
  };
}

describe("BLD-A252 J-BROWSE/4 S-R1: a desk row opened right after a sort or a search", () => {
  // The desk reads its list once on arrival, and that read lands; the sort's or search's read is still on its way
  beforeEach(() => serve(desk(ROWS)));

  it("BLD-A252 J-BROWSE/4 sort, then open a row at once: the sort is adopted with a restore; the click only pushes", async () => {
    arriveAt("/desk?tab=waiting&sort=time_left");
    act(() => root.render(createElement(DeskView, { initial: desk(ROWS) })));
    await settle();
    log.length = 0;
    const area = [...host.querySelectorAll("button")].find((b) => b.textContent === "Area")!;
    click(area);
    expect(log).toEqual(["restore /desk?tab=waiting&sort=area"]);
    click(host.querySelectorAll<HTMLAnchorElement>(".rd-title")[1]!);
    expect(log).toEqual(["restore /desk?tab=waiting&sort=area", "push /desk/ideas/IDEA-2026-000502"]);
    const { state, url } = leaving();
    expect(url).toMatch(/^\/desk\?tab=waiting&sort=area&row=IDEA-2026-000502&dy=-?\d+$/);
    expect(state.__NA).toBe(true);
    expect(state.__PRIVATE_NEXTJS_INTERNALS_TREE).toEqual(TREE);
    expect(here()).toBe(url);
  });

  it("BLD-A252 J-BROWSE/4 DEC-110 search, then open a row at once: the click only pushes, and the words stay kept", async () => {
    arriveAt("/desk?tab=waiting&sort=time_left");
    act(() => root.render(createElement(DeskView, { initial: desk(ROWS) })));
    await settle();
    log.length = 0;
    search(WORDS);
    expect(log).toEqual(["restore /desk?tab=waiting&sort=time_left"]);
    click(host.querySelectorAll<HTMLAnchorElement>(".rd-title")[1]!);
    expect(log.slice(1)).toEqual(["push /desk/ideas/IDEA-2026-000502"]);
    const { state, url } = leaving();
    expect(url).toMatch(/^\/desk\?tab=waiting&sort=time_left&row=IDEA-2026-000502&dy=-?\d+$/);
    expect(state.__NA).toBe(true);
    expect(state.__PRIVATE_NEXTJS_INTERNALS_TREE).toEqual(TREE);
    expect(state.kfinSearch).toEqual({ "/desk": WORDS });
    expect(readSearch("/desk")).toBe(WORDS);
    expect(url).not.toContain(WORDS);
  });
});

// --- S-07, My ideas ---------------------------------------------------------------------------------------------

const ROW = "IDEA-2026-000002";
const TO = `/ideas/${ROW}?from=my-ideas`;

function mine(sort: "latest" | "shared" = "latest"): MyData {
  return {
    items: [
      {
        id: ROW,
        ref: ROW,
        list: "yours",
        title: "Redemption status is not visible to the branch",
        href: TO,
        meta: `${ROW}, Shared Tuesday 17 November`,
        pill: { status: "with_review_desk", label: "With the review desk", variant: "blue" },
        track: null,
        next_step: {
          sentence: "The review desk looks at it by Tuesday 24 November.",
          action: {
            label: "See where it is",
            to: TO,
            style: "line",
            accessible_name: "See where it is: Redemption status is not visible to the branch",
          },
        },
        group: "with_review_desk",
        activity_at: "2026-11-17T10:00:00+05:30",
      },
    ],
    total: 1,
    counts: {
      all: 1,
      needs_you: 0,
      with_review_desk: 1,
      picked_and_building: 0,
      shipped: 0,
      closed: 0,
      drafts: 0,
    },
    lists: { yours: 1, teamed: 0 },
    state: { list: "yours", filter: "all", sort, q: "", row: null },
    query: "",
    url: "/my-ideas",
    tabs: [
      { list: "yours", label: "Yours", count: 1, selected: true, to: "/my-ideas" },
      { list: "teamed", label: "Teamed up", count: 0, selected: false, to: "/my-ideas?list=teamed" },
    ],
    filters: [{ filter: "all", label: "All", short_label: "All", count: 1, selected: true, to: "/my-ideas" }],
    sorts: [
      { sort: "latest", label: "Latest activity", selected: sort === "latest", to: "/my-ideas" },
      { sort: "shared", label: "Date shared", selected: sort === "shared", to: "/my-ideas?sort=shared" },
    ],
    sort_cycle: { label: "Sorted by latest activity", next: "shared", to: "/my-ideas?sort=shared" },
    copy_link: { label: "Copy link", url: "/my-ideas", done: "Link copied" },
  } as MyData;
}
const titleLink = () => host.querySelector<HTMLAnchorElement>(".mi-t a")!;

describe("BLD-A252 J-BROWSE/4 S-07: a My ideas row opened right after a sort or a search", () => {
  it("BLD-A252 J-BROWSE/4 sort, then open a row at once: the sort is adopted with a restore; the click only pushes", async () => {
    serve(); // the sort's read is still on its way when the row is clicked
    arriveAt("/my-ideas");
    act(() => root.render(createElement(MyIdeasScreen, { data: mine() })));
    await settle();
    log.length = 0;
    const shared = [...host.querySelectorAll("button")].find((b) => b.textContent === "Date shared")!;
    click(shared);
    expect(log).toEqual(["restore /my-ideas?sort=shared"]);
    click(titleLink());
    expect(log).toEqual(["restore /my-ideas?sort=shared", `push ${TO}`]);
    const { state, url } = leaving();
    expect(url).toMatch(new RegExp(`^/my-ideas\\?sort=shared&row=${ROW}&dy=-?\\d+$`));
    expect(state.__NA).toBe(true);
    expect(state.__PRIVATE_NEXTJS_INTERNALS_TREE).toEqual(TREE);
    expect(here()).toBe(url);
  });

  it("BLD-A252 J-BROWSE/4 DEC-110 search, then open a row at once: the click only pushes, and the words stay kept", async () => {
    // A search fades My ideas' list through loading rows: the row is there to click once the search's answer lands
    serve({ ...mine("shared"), state: { ...mine("shared").state, q: "Redemption" }, query: "Redemption" });
    arriveAt("/my-ideas?sort=shared");
    act(() => root.render(createElement(MyIdeasScreen, { data: mine("shared") })));
    await settle();
    log.length = 0;
    search("Redemption");
    expect(log).toEqual(["restore /my-ideas?sort=shared"]);
    await settle();
    click(titleLink());
    expect(log.slice(1)).toEqual([`push ${TO}`]);
    const { state, url } = leaving();
    expect(url).toMatch(new RegExp(`^/my-ideas\\?sort=shared&row=${ROW}&dy=-?\\d+$`));
    expect(state.__NA).toBe(true);
    expect(state.__PRIVATE_NEXTJS_INTERNALS_TREE).toEqual(TREE);
    expect(readSearch("/my-ideas")).toBe("Redemption");
    expect(url).not.toContain("Redemption");
  });
});
