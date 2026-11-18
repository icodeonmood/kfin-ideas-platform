// @vitest-environment jsdom
/**
 * S-07.state, P-ROUTES.state (J-BROWSE/1 and /3), DEC-110: on My ideas the tab, filter and sort live in the URL and
 * the search in this tab's memory of the history entry, never in a URL. Every change asks the server for its view
 * with a POST, its words in the body. Quick changes build on each other: the server's answer to a sort, tab or filter
 * must not wipe what the person typed into the search box meanwhile, and an answer to an earlier change must not
 * undo a later one still on its way: the search then goes to the server with the sort the person picked. The answer
 * to the person's own search leaves what they typed on since, and when the address moves elsewhere (Back, a link)
 * before an answer comes, the change in flight gives way. Synthetic rows only.
 */
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { readSearch, writeSearch } from "@/lib/search-memory";

const replace = vi.fn();
const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), refresh }),
  useSearchParams: () => new URLSearchParams(window.location.search),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));
// The sort's glide is motion only; run the change at once
vi.mock("@/lib/motion/flip", () => ({
  flip: (_rows: unknown, change: () => Promise<void>) => {
    void change();
    return Promise.resolve();
  },
}));

const { MyIdeasScreen } = await import("@/app/my-ideas/my-ideas-screen");
type Data = NonNullable<Parameters<typeof MyIdeasScreen>[0]["data"]>;
type State = Data["state"];

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const ROW = "IDEA-2026-000002";

function view(state: Partial<State>): Data {
  const s: State = { list: "yours", filter: "all", sort: "latest", q: "", row: null, ...state };
  const href = `/ideas/${ROW}?from=my-ideas`;
  return {
    items: [
      {
        id: ROW,
        ref: ROW,
        list: "yours",
        title: "Redemption status is not visible to the branch",
        href,
        meta: `${ROW}, Shared Tuesday 17 November`,
        pill: { status: "with_review_desk", label: "With the review desk", variant: "blue" },
        track: null,
        next_step: {
          sentence: "The review desk looks at it by Tuesday 24 November.",
          action: {
            label: "See where it is",
            to: href,
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
    state: s,
    query: "",
    url: "/my-ideas",
    tabs: [
      { list: "yours", label: "Yours", count: 1, selected: s.list === "yours", to: "/my-ideas" },
      {
        list: "teamed",
        label: "Teamed up",
        count: 0,
        selected: s.list === "teamed",
        to: "/my-ideas?list=teamed",
      },
    ],
    filters: [{ filter: "all", label: "All", short_label: "All", count: 1, selected: true, to: "/my-ideas" }],
    sorts: [
      { sort: "latest", label: "Latest activity", selected: s.sort === "latest", to: "/my-ideas" },
      { sort: "shared", label: "Date shared", selected: s.sort === "shared", to: "/my-ideas?sort=shared" },
    ],
    sort_cycle: { label: "Sorted by latest activity", next: "shared", to: "/my-ideas?sort=shared" },
    copy_link: { label: "Copy link", url: "/my-ideas", done: "Link copied" },
    ...(s.row ? { arrival: { line: "Back where you were: Yours.", row: s.row } } : {}),
  } as Data;
}

/** Every read the screen asks for, held until the test answers it, in any order. */
type Asked = { url: string; init: RequestInit; resolve: (res: Response) => void };
let asked: Asked[] = [];

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  replace.mockClear();
  refresh.mockClear();
  asked = [];
  window.history.replaceState(null, "", "/my-ideas");
  vi.stubGlobal(
    "fetch",
    vi.fn(
      (url: string, init: RequestInit = {}) =>
        new Promise<Response>((resolve) => asked.push({ url: String(url), init, resolve })),
    ),
  );
  Element.prototype.scrollIntoView = vi.fn(); // jsdom draws no layout
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

async function flush() {
  for (let i = 0; i < 8; i++) await act(async () => await Promise.resolve());
}
function render(data: Data) {
  act(() => root.render(createElement(MyIdeasScreen, { data })));
}
/** The server answers the read asked `i`-th with `data`, or fails it. */
async function answer(i: number, data: Data | null) {
  await act(async () => {
    asked[i]!.resolve(
      data
        ? new Response(JSON.stringify(data), { status: 200 })
        : new Response(JSON.stringify({ error: { code: "unavailable" } }), { status: 503 }),
    );
  });
  await flush();
}
const bodyOf = (i: number) => JSON.parse(String(asked[i]!.init.body)) as Record<string, string>;
const lastBody = () => bodyOf(asked.length - 1);
const here = () => window.location.pathname + window.location.search;

function box(): HTMLInputElement {
  return host.querySelector<HTMLInputElement>('input[type="search"]')!;
}
function type(value: string) {
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  act(() => {
    set.call(box(), value);
    box().dispatchEvent(new Event("input", { bubbles: true }));
  });
}
function submit() {
  act(() => {
    box().form!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  });
}
function clickSort(label: string) {
  const b = [...host.querySelectorAll("button")].find((x) => x.textContent === label)!;
  act(() => b.click());
}
function clickTab(label: string) {
  const t = [...host.querySelectorAll<HTMLElement>('[role="tab"]')].find((x) =>
    x.textContent?.startsWith(label),
  )!;
  act(() => t.click());
}
/** The page moves to `href` and renders its view, as Next does for a link or the router's cached page. */
function arrive(href: string, state: Partial<State>) {
  window.history.replaceState(null, "", href);
  render(view(state));
}
const pressed = (label: string) =>
  [...host.querySelectorAll("button")].find((x) => x.textContent === label)?.getAttribute("aria-pressed");

describe("S-07.state, P-ROUTES.state (J-BROWSE/1): quick changes on My ideas build on each other", () => {
  it("the answer to a sort keeps what the person typed meanwhile, and Enter keeps the sort", async () => {
    render(view({}));
    clickSort("Date shared");
    expect(here()).toBe("/my-ideas?sort=shared");
    expect(lastBody()).toEqual({ list: "yours", filter: "all", sort: "shared", q: "" });
    type("Redemption");
    await answer(0, view({ sort: "shared" })); // the sort's answer arrives while the search is being typed
    expect(box().value).toBe("Redemption");
    submit();
    // DEC-110: the search goes in the body and this tab's memory; the address keeps the sort only
    expect(lastBody()).toEqual({ list: "yours", filter: "all", sort: "shared", q: "Redemption" });
    expect(here()).toBe("/my-ideas?sort=shared");
    expect(readSearch("/my-ideas")).toBe("Redemption");
  });

  it("an answer to an earlier change does not undo a later one still on its way", async () => {
    render(view({}));
    act(() => host.querySelector<HTMLButtonElement>('[role="tab"]')!.click()); // Yours, already the tab
    clickSort("Date shared");
    type("Redemption");
    await answer(0, view({})); // the tab's answer, from before the sort
    expect(box().value).toBe("Redemption");
    expect(pressed("Date shared")).toBe("true");
    submit();
    expect(lastBody()).toMatchObject({ sort: "shared", q: "Redemption" });
    expect(here()).toBe("/my-ideas?sort=shared");
  });

  it("the answer to the person's own search leaves what they typed on since (S-07.state)", async () => {
    render(view({}));
    type("abc");
    submit();
    expect(lastBody()).toMatchObject({ q: "abc" });
    type("abcd"); // still typing when the answer for "abc" lands
    await answer(asked.length - 1, view({ q: "abc" }));
    expect(box().value).toBe("abcd");
    submit();
    expect(lastBody()).toMatchObject({ q: "abcd" });
    expect(here()).toBe("/my-ideas");
  });

  it("Clear on the screen empties the box at once, and its answer leaves it empty", async () => {
    const none = (v: Data): Data => ({
      ...v,
      items: [],
      empty: {
        kind: "no_results",
        title: "Nothing matches “abc”",
        line: "",
        actions: [{ label: "Clear", to: "/my-ideas" }],
      },
    });
    writeSearch("/my-ideas", "abc"); // the entry keeps a search: the screen asks for it on arrival
    render(view({}));
    expect(box().value).toBe("abc");
    expect(bodyOf(0)).toMatchObject({ q: "abc" });
    await answer(0, none(view({ q: "abc" })));
    const clear = [...host.querySelectorAll(".mi-emptyc button")].find((x) => x.textContent === "Clear")!;
    act(() => (clear as HTMLButtonElement).click());
    expect(lastBody()).toMatchObject({ q: "" });
    expect(box().value).toBe("");
    expect(readSearch("/my-ideas")).toBe("");
    await answer(asked.length - 1, view({}));
    expect(box().value).toBe("");
  });

  it("DEC-110: the search a history entry keeps puts its words in the box; a fresh entry has none", async () => {
    writeSearch("/my-ideas", "Redemption");
    render(view({}));
    expect(box().value).toBe("Redemption");
    await answer(0, view({ q: "Redemption" }));
    window.history.pushState(null, "", "/my-ideas"); // the sidebar, a link: a new entry
    render(view({}));
    expect(box().value).toBe("");
    writeSearch("/my-ideas", "SMS");
    render(view({}));
    expect(box().value).toBe("SMS");
  });
});

describe("P-ROUTES.state, S-07.state: a change in flight gives way when the address moves elsewhere", () => {
  it("Back before the sort's answer: the screen shows the view it has, and the next change builds on that", async () => {
    render(view({}));
    clickSort("Date shared");
    expect(pressed("Date shared")).toBe("true");
    window.history.replaceState(null, "", "/my-ideas"); // Back: the entry before, with nothing in it
    act(() => window.dispatchEvent(new PopStateEvent("popstate")));
    await act(async () => await new Promise((r) => setTimeout(r, 0)));
    expect(pressed("Latest activity")).toBe("true");
    await answer(0, view({ sort: "shared" })); // the sort's answer, too late
    expect(pressed("Latest activity")).toBe("true");
    type("Redemption");
    submit();
    expect(lastBody()).toMatchObject({ sort: "latest", q: "Redemption" });
    expect(here()).toBe("/my-ideas");
  });

  it("a link to another view before the answer: that view stands, not the change asked for", async () => {
    render(view({}));
    clickSort("Date shared");
    arrive("/my-ideas?list=teamed", { list: "teamed" }); // a link elsewhere lands first
    expect(pressed("Latest activity")).toBe("true");
    await answer(0, view({ sort: "shared" }));
    expect(pressed("Latest activity")).toBe("true");
    type("Redemption");
    submit();
    expect(lastBody()).toMatchObject({ list: "teamed", sort: "latest", q: "Redemption" });
    expect(here()).toBe("/my-ideas?list=teamed");
  });

  it("an earlier change of the person's that answers late does not undo a later change still on its way", async () => {
    render(view({}));
    clickTab("Teamed up");
    clickSort("Date shared");
    await answer(0, view({ list: "teamed" })); // the tab's answer, from before the sort
    expect(pressed("Date shared")).toBe("true");
    type("Redemption");
    submit();
    expect(lastBody()).toMatchObject({ list: "teamed", sort: "shared", q: "Redemption" });
    expect(here()).toBe("/my-ideas?list=teamed&sort=shared");
  });
});

describe("DEC-110, J-BROWSE/3, S-07.return: the search comes back with the entry, and never goes in a URL", () => {
  it("Back from an idea: the list is held as loading until the searched view lands, then the row comes back", async () => {
    writeSearch("/my-ideas", "Redemption");
    window.history.replaceState(window.history.state, "", `/my-ideas?sort=shared&row=${ROW}&dy=140`);
    render(view({ sort: "shared", row: ROW })); // the router's page for the address, without the search
    expect(host.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(host.querySelector(`[data-row="${ROW}"]`)).toBeNull(); // the unsearched list never stands in
    expect(bodyOf(0)).toEqual({ list: "yours", filter: "all", sort: "shared", q: "Redemption", row: ROW });
    // a frame passes before the answer: the row waits for the list it was opened from
    await act(async () => await new Promise<void>((r) => requestAnimationFrame(() => r())));
    expect(here()).toBe(`/my-ideas?sort=shared&row=${ROW}&dy=140`);
    await answer(0, view({ sort: "shared", q: "Redemption", row: ROW }));
    await act(async () => await new Promise<void>((r) => requestAnimationFrame(() => r())));
    expect(host.textContent).toContain("Back where you were: Yours.");
    expect(here()).toBe("/my-ideas?sort=shared"); // the row and its offset leave; the search was never there
    expect(box().value).toBe("Redemption");
    expect(readSearch("/my-ideas")).toBe("Redemption");
  });

  it("J-BROWSE/3: a row opened while an answer or the router's read is on its way leaves the address Back returns to", async () => {
    render(view({}));
    writeSearch("/my-ideas", "");
    clickSort("Date shared"); // the rows stay on screen while a sort's answer comes
    const link = host.querySelector<HTMLAnchorElement>(`[data-row="${ROW}"] h3 a`)!;
    act(() => link.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 })));
    expect(here()).toMatch(new RegExp(`^/my-ideas\\?sort=shared&row=${ROW}&dy=-?\\d+$`));
    const opened = here();
    await answer(0, view({ sort: "shared", row: ROW })); // lands after the row was opened
    render(view({ sort: "shared", row: ROW })); // the router's read of the address with the row in it
    await act(async () => await new Promise<void>((r) => requestAnimationFrame(() => r())));
    expect(here()).toBe(opened);
    expect(host.textContent).not.toContain("Back where you were");
    expect(asked).toHaveLength(1);
  });

  it("every read with a search is a POST to /api/me/ideas; no request URL and no address holds the words", async () => {
    render(view({}));
    type("Zebra7Kestrel");
    submit();
    clickSort("Date shared");
    clickTab("Teamed up");
    expect(asked.length).toBe(3);
    for (const a of asked) {
      expect(a.url).toBe("/api/me/ideas");
      expect(a.init.method).toBe("POST");
    }
    expect(asked.map((a) => a.url).join(" ")).not.toMatch(/zebra7kestrel/i);
    expect(here()).not.toMatch(/zebra7kestrel/i);
    expect(replace).not.toHaveBeenCalled();
  });

  it("DEC-110: the arrival read with the kept words fails: they stay kept, and no unsearched row or count shows under them", async () => {
    writeSearch("/my-ideas", "Redemption");
    window.history.replaceState(window.history.state, "", `/my-ideas?row=${ROW}&dy=40`);
    render(view({ row: ROW }));
    await answer(0, null);
    await act(async () => await new Promise<void>((r) => requestAnimationFrame(() => r())));
    expect(readSearch("/my-ideas")).toBe("Redemption");
    expect(box().value).toBe("Redemption");
    expect(host.querySelector(`[data-row="${ROW}"]`)).toBeNull();
    expect([...host.querySelectorAll('[role="tab"]')].map((t) => t.textContent)).toEqual([
      "Yours",
      "Teamed up",
    ]);
    expect(host.textContent).toContain("We can't load your ideas just now. Please try again in a minute.");
    // the row stays in the address for a reload to place
    expect(here()).toBe(`/my-ideas?row=${ROW}&dy=40`);
    // Enter asks again with the same words
    submit();
    expect(lastBody()).toMatchObject({ q: "Redemption" });
    await answer(1, view({ q: "Redemption" }));
    expect(host.querySelector(`[data-row="${ROW}"]`)).not.toBeNull();
    expect(host.textContent).not.toContain("We can't load your ideas just now.");
  });

  it("a view that could not be read leaves the list, the address and the memory as they were; the box keeps the words", async () => {
    render(view({}));
    type("abc");
    submit();
    await answer(0, null);
    expect(host.textContent).toContain("We can't load your ideas just now. Please try again in a minute.");
    expect(box().value).toBe("abc");
    expect(readSearch("/my-ideas")).toBe("");
    expect(here()).toBe("/my-ideas");
    expect(host.querySelector(`[data-row="${ROW}"]`)).not.toBeNull();
  });
});
