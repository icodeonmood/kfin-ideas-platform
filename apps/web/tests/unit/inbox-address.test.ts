// @vitest-environment jsdom
/**
 * S-H5, C-INBOX-READER, P-ROUTES.state (J-BROWSE/4 and /6): the Inbox keeps its tab and the open item in the
 * address, and its search in this tab's memory of the history entry, never the address (DEC-110). The reader writes
 * them with history.replaceState as the person moves; the server reads the address on a reload or a link; and Back
 * to an Inbox the router kept from before the address moved loads what the address names. An unknown tab or item
 * falls back to the default, and an item opens only if it is in the person's own list. Synthetic people and ideas.
 */
import { act, createElement } from "react";
import { createRoot, hydrateRoot, type Root } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { InboxCounts, InboxEntry, InboxList } from "@/server/inbox";

const state = vi.hoisted(() => ({
  me: { id: "u-tanvi" } as unknown,
  lists: {} as Record<string, unknown>,
  asked: [] as string[],
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: () => undefined }),
  useSearchParams: () => new URLSearchParams(globalThis.location?.search ?? ""),
  redirect: (to: string) => {
    throw new Error(`redirect ${to}`);
  },
}));
vi.mock("next/link", async () => {
  const { createElement: h } = await import("react");
  return {
    default: (p: { href: string; className?: string; children?: unknown }) =>
      h("a", { href: p.href, className: p.className }, p.children as never),
  };
});
vi.mock("@/server/auth/current", () => ({ currentUser: async () => state.me }));
vi.mock("@/server/inbox", () => ({
  isItemId: (id: string) => /^[0-9]{1,18}$/.test(id),
  // The worker scopes every list to the person; the pages never ask for one item by itself.
  inboxFor: async (_me: unknown, tab: string) => {
    state.asked.push(tab);
    return state.lists[tab];
  },
}));

import { inboxHref, itemIn, readInboxAddress, type InboxView } from "@/app/inbox/address";
import { readSearch, writeSearch } from "@/lib/search-memory";
import { InboxReader, startView } from "@/app/inbox/inbox-reader";
import InboxItemPage from "@/app/inbox/[item]/page";
import Inbox from "@/app/inbox/page";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const QUESTIONS: InboxEntry = {
  id: "7",
  kind: "questions",
  from: { id: "u-harish", name: "Harish Kulkarni", first_name: "Harish", initials: "HK" },
  idea: {
    id: "IDEA-2026-000901",
    title: "Branch staff cannot see SIP pause requests",
    status: "with_review_desk",
  },
  line: "asked you 3 questions",
  at: new Date().toISOString(),
  unread: false,
  needs_you: true,
  archived: false,
  body: {
    heading: "Questions from the review desk",
    note: "",
    sender: "Harish from the review desk",
    set_id: "s-1",
  },
  actions: [{ label: "Answer the questions", style: "primary", to: "/ideas/IDEA-2026-000901/answer" }],
} as InboxEntry;

const MENTION: InboxEntry = {
  ...QUESTIONS,
  id: "8",
  kind: "mention",
  line: "mentioned you",
  unread: true,
  needs_you: false,
  body: { heading: "", note: "", sender: "Zoya Siddiqui" },
  actions: [],
} as InboxEntry;

const COUNTS: InboxCounts = { all: 2, needs_you: 1, unread: 1, archived: 0 };
const list = (items: InboxEntry[]): InboxList => ({ items, total: items.length, counts: COUNTS, unread: 1 });
const ALL = list([MENTION, QUESTIONS]);
const NEEDS_YOU = list([QUESTIONS]);

let host: HTMLElement;
let root: Root;
let calls: string[];

function stubWidth(desktop: boolean) {
  window.matchMedia = ((q: string) => ({
    matches: desktop,
    media: q,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  })) as unknown as typeof window.matchMedia;
}

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  calls = [];
  state.asked = [];
  state.lists = { all: ALL, needs_you: NEEDS_YOU, unread: list([MENTION]), archived: list([]) };
  stubWidth(true);
  window.history.replaceState(null, "", "/inbox");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      const tab = /^\/api\/inbox\?tab=(\w+)$/.exec(url)?.[1];
      if (tab) return new Response(JSON.stringify(state.lists[tab]), { status: 200 });
      if (/^\/api\/inbox\/\d+\/read$/.test(url)) return new Response(JSON.stringify(COUNTS), { status: 200 });
      return new Response(JSON.stringify({ error: { code: "not_found" } }), { status: 404 });
    }),
  );
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

async function settle() {
  for (let i = 0; i < 6; i++) await act(async () => await Promise.resolve());
  // The reader loads the address's own tab a turn after it arrives
  if (!vi.isFakeTimers()) await act(async () => await new Promise((r) => setTimeout(r, 5)));
  for (let i = 0; i < 6; i++) await act(async () => await Promise.resolve());
}

async function show(initial: InboxList, initialTab: "all" | "needs_you", initialItem: string | null) {
  await act(async () => {
    root.render(createElement(InboxReader, { initial, initialTab, initialItem }));
  });
  await settle();
}

const tab = (id: string) => host.querySelector<HTMLButtonElement>(`#ibx-tab-${id}`)!;
const row = (id: string) => host.querySelector<HTMLButtonElement>(`#ibx-row-${id}`);
const here = () => window.location.pathname + window.location.search;

describe("S-H5 address: what it reads and writes (P-ROUTES.state)", () => {
  it("J-BROWSE/4, DEC-110: the tab and the open item go in and come back out the same; the search never goes in", () => {
    const view: InboxView = { tab: "needs_you", item: "7", q: "sip pause" };
    const href = inboxHref("/inbox", view);
    expect(href).toBe("/inbox?tab=needs_you&item=7");
    expect(href).not.toMatch(/sip|pause|q=/);
    expect(readInboxAddress(new URL(href, "http://x").searchParams)).toEqual({
      named: true,
      tab: "needs_you",
      item: "7",
    });
    // An older address's search is not read (J-BROWSE/6), and a search alone names no view
    expect(readInboxAddress(new URLSearchParams("tab=all&q=sip"))).toEqual({
      named: true,
      tab: "all",
      item: null,
    });
    expect(readInboxAddress(new URLSearchParams("q=sip")).named).toBe(false);
    // An item's own address keeps its path; anything else is the Inbox
    expect(inboxHref("/inbox/41", { tab: "all", item: null })).toBe("/inbox/41?tab=all");
    expect(inboxHref("/desk", { tab: "all", item: null })).toBe("/inbox?tab=all");
    expect(readInboxAddress({ tab: ["unread", "all"] }).tab).toBe("unread");
  });

  it("an unknown tab or item falls back to the default without an error", () => {
    expect(readInboxAddress(new URLSearchParams("tab=starred&item=../9"))).toEqual({
      named: true,
      tab: "all",
      item: null,
    });
    expect(readInboxAddress(new URLSearchParams(""))).toMatchObject({ named: false, tab: "all", item: null });
    expect(readInboxAddress({ item: "1".repeat(19) }).item).toBeNull();
    expect(itemIn("9", ALL.items)).toBeNull();
    expect(itemIn("7", ALL.items)).toBe("7");
  });

  it("startView: the page's props when the address names nothing or the same tab; a reload when Back brings an older page", () => {
    const initial = { tab: "all" as const, item: null, items: ALL.items };
    expect(startView(new URLSearchParams(""), { ...initial, item: "7" })).toEqual({
      tab: "all",
      item: "7",
      q: "",
      reload: false,
    });
    // DEC-110: a link's search is not taken; the reader reads this tab's memory once it has mounted
    expect(startView(new URLSearchParams("tab=all&item=7&q=sip"), initial)).toEqual({
      tab: "all",
      item: "7",
      q: "",
      reload: false,
    });
    expect(startView(new URLSearchParams("tab=all&item=9"), initial).item).toBeNull(); // not the person's
    expect(startView(new URLSearchParams("tab=needs_you&item=7"), initial)).toMatchObject({
      tab: "needs_you",
      reload: true,
    });
  });
});

describe("S-H5, C-INBOX-READER: the reader keeps the view in the address (J-BROWSE/4)", () => {
  it("a tab and an item go into the address; Back to the router's older page restores both, marking nothing else read", async () => {
    await show(ALL, "all", null);
    await act(async () => tab("needs_you").click());
    await settle();
    expect(here()).toBe("/inbox?tab=needs_you");
    expect(calls).toContain("GET /api/inbox?tab=needs_you");

    await act(async () => row("7")!.click());
    expect(here()).toBe("/inbox?tab=needs_you&item=7");

    // The person opens "Answer the questions" and comes Back: the router hands over the page it rendered for /inbox
    act(() => root.unmount());
    root = createRoot(host);
    calls = [];
    await show(ALL, "all", null);
    expect(tab("needs_you").getAttribute("aria-selected")).toBe("true");
    expect(calls).toContain("GET /api/inbox?tab=needs_you");
    expect(row("7")?.getAttribute("aria-pressed")).toBe("true");
    expect(row("8")).toBeNull();
    expect(calls.filter((c) => c.startsWith("POST"))).toEqual([]); // the cached list's first item was never opened
    expect(here()).toBe("/inbox?tab=needs_you&item=7");
  });

  it("Back or Forward to the Inbox loads its list again before opening anything, so nothing stale is marked read", async () => {
    const staleMention = { ...MENTION, unread: true };
    state.lists.all = list([{ ...MENTION, unread: false }, QUESTIONS]); // read since the router kept its page
    window.history.replaceState(null, "", "/inbox?tab=all&item=8");
    window.dispatchEvent(new PopStateEvent("popstate"));
    await show(list([staleMention, QUESTIONS]), "all", null);
    expect(calls).toContain("GET /api/inbox?tab=all");
    expect(calls.filter((c) => c.startsWith("POST"))).toEqual([]);
    expect(row("8")?.getAttribute("aria-pressed")).toBe("true");
    expect(row("8")?.className).not.toContain(" un");

    // An ordinary arrival (no Back) uses the page as the server rendered it
    act(() => root.unmount());
    root = createRoot(host);
    calls = [];
    await show(ALL, "all", null);
    expect(calls.filter((c) => c.startsWith("GET /api/inbox?"))).toEqual([]);
  });

  it("a count refresh that lands late with the older address does not undo the view", async () => {
    await show(ALL, "all", null);
    expect(here()).toBe("/inbox"); // nothing is written until the person moves
    await act(async () => tab("needs_you").click());
    await settle();
    expect(here()).toBe("/inbox?tab=needs_you");
    // The router puts back the address its refresh started from, and renders the page again
    window.history.replaceState(null, "", "/inbox");
    await show(ALL, "all", null);
    expect(here()).toBe("/inbox?tab=needs_you");
    expect(tab("needs_you").getAttribute("aria-selected")).toBe("true");
  });

  it("DEC-110, J-BROWSE/1 and /3: a search stays in this tab's memory, never the address, and comes back with the page", async () => {
    await show(ALL, "all", null);
    const input = host.querySelector<HTMLInputElement>('input[type="search"]')!;
    expect(input.getAttribute("autocomplete")).toBe("off");
    await act(async () => {
      const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
      set.call(input, "Zoya");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    // kept at once, so a link opened straight after leaves it behind for Back
    expect(readSearch("/inbox")).toBe("Zoya");
    expect(here()).toBe("/inbox?tab=all");
    expect(row("8")).not.toBeNull();
    expect(row("7")).toBeNull();
    expect(calls.filter((c) => /zoya/i.test(c))).toEqual([]);

    // Back or a reload: the same entry, so the same search and the same filtered list
    act(() => root.unmount());
    root = createRoot(host);
    await show(ALL, "all", null);
    expect(host.querySelector<HTMLInputElement>('input[type="search"]')!.value).toBe("Zoya");
    expect(row("7")).toBeNull();

    // A fresh visit (the sidebar, a link) is a new entry: no search (J-BROWSE/6)
    act(() => root.unmount());
    root = createRoot(host);
    window.history.pushState(null, "", "/inbox");
    await show(ALL, "all", null);
    expect(host.querySelector<HTMLInputElement>('input[type="search"]')!.value).toBe("");
    expect(row("7")).not.toBeNull();
  });

  it("DEC-110: an older address's ?q= leaves the address and is not taken as the search", async () => {
    window.history.replaceState(null, "", "/inbox?tab=all&q=Zoya");
    await show(ALL, "all", null);
    expect(here()).toBe("/inbox?tab=all");
    expect(host.querySelector<HTMLInputElement>('input[type="search"]')!.value).toBe("");
  });

  it("DEC-110: nothing from the unfiltered list is opened or marked read before the kept search is back", async () => {
    writeSearch("/inbox", "Harish"); // matches the questions (read) and not the mention (unread, first in the list)
    await show(ALL, "all", null);
    expect(host.querySelector<HTMLInputElement>('input[type="search"]')!.value).toBe("Harish");
    expect(row("8")).toBeNull();
    expect(row("7")?.getAttribute("aria-pressed")).toBe("true");
    expect(calls.filter((c) => c.startsWith("POST"))).toEqual([]);
  });

  it("DEC-110, L-QUESTIONS.clock/1: a hydrating page never reads a question set the kept search hides (the first read marks it seen for the desk)", async () => {
    // Questions first, so the unfiltered list the server renders opens them on a desktop; the kept words match only
    // the mention, so the person never sees the questions on this load.
    const first = list([QUESTIONS, MENTION]);
    state.lists = { ...state.lists, all: first };
    writeSearch("/inbox", "Zoya");
    const el = createElement(InboxReader, { initial: first, initialTab: "all", initialItem: null });
    act(() => root.unmount());
    host.innerHTML = renderToString(el);
    await act(async () => {
      root = hydrateRoot(host, el, { onRecoverableError: () => undefined });
    });
    await settle();
    expect(host.querySelector<HTMLInputElement>('input[type="search"]')!.value).toBe("Zoya");
    expect(row("7")).toBeNull();
    expect(calls.filter((c) => c.includes("question-set"))).toEqual([]);
    // The item the search keeps opens and is read as usual (S-H5.rules/2); the hidden questions are never touched
    expect(calls.filter((c) => c.startsWith("POST"))).toEqual(["POST /api/inbox/8/read"]);
    expect(calls.some((c) => c.includes("/inbox/7/"))).toBe(false);
  });

  it("an item the address names that is not in the person's list opens nothing and is never asked for", async () => {
    window.history.replaceState(null, "", "/inbox?tab=needs_you&item=999");
    await show(ALL, "all", null);
    expect(tab("needs_you").getAttribute("aria-selected")).toBe("true");
    expect(calls.some((c) => c.includes("999"))).toBe(false);
    expect(here()).toBe("/inbox?tab=needs_you"); // the address drops what it could not open
  });

  it("S-H5.rules/6: on a phone, Back to the list marks nothing read; Back to an item the person had open shows it again", async () => {
    stubWidth(false);
    window.history.replaceState(null, "", "/inbox?tab=all");
    await show(ALL, "all", null);
    expect(host.querySelector(".ibx-reading")).toBeNull();
    expect(calls.filter((c) => c.startsWith("POST"))).toEqual([]);

    act(() => root.unmount());
    root = createRoot(host);
    window.history.replaceState(null, "", "/inbox?tab=needs_you&item=7");
    await show(ALL, "all", null);
    expect(host.querySelector(".ibx-reading")).not.toBeNull();
    expect(host.querySelector("h1#ibx-title")?.textContent).toBe(QUESTIONS.idea!.title);

    await act(async () => host.querySelector<HTMLButtonElement>(".ibx-back")!.click());
    expect(here()).toBe("/inbox?tab=needs_you");
  });
});

describe("S-H5, S-H2B pages: a reload or a link shows the view its address names (J-BROWSE/6)", () => {
  it("/inbox reads the tab and the item, and opens the item only from the person's own list", async () => {
    const el = await Inbox({ searchParams: Promise.resolve({ tab: "needs_you", item: "7" }) });
    expect(el.type).toBe(InboxReader);
    expect(el.props).toMatchObject({ initialTab: "needs_you", initialItem: "7", initial: NEEDS_YOU });

    const other = await Inbox({ searchParams: Promise.resolve({ tab: "needs_you", item: "8" }) });
    expect(other.props).toMatchObject({ initialTab: "needs_you", initialItem: null }); // not in that list

    const odd = await Inbox({ searchParams: Promise.resolve({ tab: "starred", item: "x" }) });
    expect(odd.props).toMatchObject({ initialTab: "all", initialItem: null });
    expect(state.asked).toEqual(["needs_you", "needs_you", "all"]);
  });

  it("/inbox/:itemId opens its item until the person moves; then its query is the view", async () => {
    const plain = await InboxItemPage({
      params: Promise.resolve({ item: "8" }),
      searchParams: Promise.resolve({}),
    });
    expect(plain.props).toMatchObject({ initialTab: "all", initialItem: "8" });

    const moved = await InboxItemPage({
      params: Promise.resolve({ item: "8" }),
      searchParams: Promise.resolve({ tab: "needs_you" }),
    });
    expect(moved.props).toMatchObject({ initialTab: "needs_you", initialItem: null, initial: NEEDS_YOU });
  });
});
