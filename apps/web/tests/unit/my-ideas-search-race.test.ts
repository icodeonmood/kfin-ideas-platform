// @vitest-environment jsdom
/**
 * S-07.state, P-ROUTES.state (J-BROWSE/1): on My ideas the list state lives in the URL, and quick changes build on
 * each other. The server's answer to a sort, tab or filter must not wipe what the person typed into the search box
 * meanwhile, and an answer to an earlier change must not undo a later one still on its way: the search then goes
 * into the address with the sort the person picked. The answer to the person's own search leaves what they typed
 * on since, and when the address moves elsewhere (Back, a link) before an answer comes, the change in flight gives
 * way. Synthetic rows only.
 */
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
// The address the page is at; Next moves it with the answer, so a test moves it with the view it renders
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => search,
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

function view(state: Partial<State>): Data {
  const s: State = { list: "yours", filter: "all", sort: "latest", q: "", row: null, ...state };
  const href = `/ideas/IDEA-2026-000002?from=my-ideas`;
  return {
    items: [
      {
        id: "IDEA-2026-000002",
        ref: "IDEA-2026-000002",
        list: "yours",
        title: "Redemption status is not visible to the branch",
        href,
        meta: "IDEA-2026-000002, Shared Tuesday 17 November",
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
  } as Data;
}

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  replace.mockClear();
  search = new URLSearchParams();
  Element.prototype.scrollIntoView = vi.fn(); // jsdom draws no layout
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

function render(data: Data) {
  act(() => root.render(createElement(MyIdeasScreen, { data })));
}
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
/** The page moves to `href` and renders its view, as Next does for Back, a link or the answer to a replace. */
function arrive(href: string, state: Partial<State>) {
  search = new URL(href, "http://x").searchParams;
  render(view(state));
}
const pressed = (label: string) =>
  [...host.querySelectorAll("button")].find((x) => x.textContent === label)?.getAttribute("aria-pressed");
const last = () => String(replace.mock.calls.at(-1)?.[0]);

describe("S-07.state, P-ROUTES.state (J-BROWSE/1): quick changes on My ideas build on each other", () => {
  it("the answer to a sort keeps what the person typed meanwhile, and Enter keeps the sort", () => {
    render(view({}));
    clickSort("Date shared");
    expect(last()).toBe("/my-ideas?sort=shared");
    type("Redemption");
    render(view({ sort: "shared" })); // the sort's answer arrives while the search is being typed
    expect(box().value).toBe("Redemption");
    submit();
    expect(last()).toBe("/my-ideas?sort=shared&q=Redemption");
  });

  it("an answer to an earlier change does not undo a later one still on its way", () => {
    render(view({}));
    act(() => host.querySelector<HTMLButtonElement>('[role="tab"]')!.click()); // Yours, already the tab
    clickSort("Date shared");
    type("Redemption");
    render(view({})); // the tab's answer, from before the sort
    expect(box().value).toBe("Redemption");
    submit();
    expect(last()).toBe("/my-ideas?sort=shared&q=Redemption");
  });

  it("the answer to the person's own search leaves what they typed on since (S-07.state)", () => {
    render(view({}));
    type("abc");
    submit();
    expect(last()).toBe("/my-ideas?q=abc");
    type("abcd"); // still typing when the answer for "abc" lands
    arrive("/my-ideas?q=abc", { q: "abc" });
    expect(box().value).toBe("abcd");
    submit();
    expect(last()).toBe("/my-ideas?q=abcd");
  });

  it("Clear on the screen empties the box at once, and its answer leaves it empty", () => {
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
    search = new URLSearchParams("q=abc");
    render(none(view({ q: "abc" })));
    expect(box().value).toBe("abc");
    const clear = [...host.querySelectorAll(".mi-emptyc button")].find((x) => x.textContent === "Clear")!;
    act(() => (clear as HTMLButtonElement).click());
    expect(last()).toBe("/my-ideas");
    expect(box().value).toBe("");
    arrive("/my-ideas", {});
    expect(box().value).toBe("");
  });

  it("a new search from the server, Clear or a link, puts the server's words in the box", () => {
    render(view({ q: "Redemption" }));
    expect(box().value).toBe("Redemption");
    render(view({ q: "" }));
    expect(box().value).toBe("");
    render(view({ q: "SMS" }));
    expect(box().value).toBe("SMS");
  });
});

describe("P-ROUTES.state, S-07.state: a change in flight gives way when the address moves elsewhere", () => {
  it("Back before the sort's answer: the screen shows the view it has, and the next change builds on that", () => {
    render(view({}));
    clickSort("Date shared");
    expect(pressed("Date shared")).toBe("true");
    act(() => window.dispatchEvent(new PopStateEvent("popstate")));
    expect(pressed("Latest activity")).toBe("true");
    type("Redemption");
    submit();
    expect(last()).toBe("/my-ideas?q=Redemption");
  });

  it("a link to another view before the answer: that view stands, not the change asked for", () => {
    render(view({}));
    clickSort("Date shared");
    arrive("/my-ideas?list=teamed", { list: "teamed" }); // a link elsewhere lands first
    expect(pressed("Latest activity")).toBe("true");
    type("Redemption");
    submit();
    expect(last()).toBe("/my-ideas?list=teamed&q=Redemption");
  });

  it("the address an earlier change of the person's put there is theirs: a later change still on its way stands", () => {
    render(view({}));
    clickTab("Teamed up");
    clickSort("Date shared");
    arrive("/my-ideas?list=teamed", { list: "teamed" }); // the tab's answer, from before the sort
    expect(pressed("Date shared")).toBe("true");
    type("Redemption");
    submit();
    expect(last()).toBe("/my-ideas?list=teamed&sort=shared&q=Redemption");
  });
});
