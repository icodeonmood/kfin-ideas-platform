// @vitest-environment jsdom
/**
 * DEC-110, BLD-A218 (P-ROUTES.state, J-BROWSE/1, /3 and /6): search words live in the tab's own page memory of the
 * history entry, never in a URL, localStorage or a cookie. The shared helper for S-07, S-R1 and S-H5. Synthetic
 * words only.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  backToSearchedList,
  cleanAddress,
  listOf,
  nextParam,
  readSearch,
  replaceAddress,
  SEARCH_MAX,
  withoutSearch,
  writeSearch,
} from "@/lib/search-memory";

const WORDS = "Zebra7Kestrel rejection SMS";

type Entry = { key: string; index: number; url: string };
/** A stand-in for the Navigation API: entries with stable keys, the current one, and how this page arrived. */
function navigation(entries: Entry[], at: number, activation?: { key: string; type: string }) {
  const nav = {
    currentEntry: entries[at]!,
    canGoBack: at > 0,
    entries: () => entries,
    activation: activation ? { entry: { key: activation.key }, navigationType: activation.type } : undefined,
  };
  Object.defineProperty(window, "navigation", { value: nav, configurable: true, writable: true });
  return nav;
}

/** This browser's storage, in memory, fresh for each test (Node's own `localStorage` is not a browser's). */
function memoryStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() {
      return m.size;
    },
    clear: () => m.clear(),
    getItem: (k: string) => m.get(k) ?? null,
    key: (i: number) => [...m.keys()][i] ?? null,
    removeItem: (k: string) => void m.delete(k),
    setItem: (k: string, v: string) => void m.set(k, String(v)),
  };
}

beforeEach(() => {
  for (const name of ["sessionStorage", "localStorage"] as const) {
    Object.defineProperty(window, name, { value: memoryStorage(), configurable: true, writable: true });
  }
  window.history.replaceState(null, "", "/my-ideas");
});
afterEach(() => {
  delete (window as { navigation?: unknown }).navigation;
  vi.restoreAllMocks();
});

describe("DEC-110: the words stay in this history entry's memory", () => {
  it("DEC-110 S-07 kept, read back and forgotten for the entry, with the address untouched", () => {
    expect(readSearch("/my-ideas")).toBe("");
    writeSearch("/my-ideas", WORDS);
    expect(readSearch("/my-ideas")).toBe(WORDS);
    expect(window.location.pathname + window.location.search).toBe("/my-ideas");
    expect((window.history.state as { kfinSearch: Record<string, string> }).kfinSearch["/my-ideas"]).toBe(
      WORDS,
    );
    // another list's search is its own
    expect(readSearch("/desk")).toBe("");
    writeSearch("/my-ideas", "");
    expect(readSearch("/my-ideas")).toBe("");
  });

  it("DEC-110 keeps the search box's limit of 200 characters", () => {
    writeSearch("/desk", "a".repeat(250));
    expect(readSearch("/desk")).toHaveLength(SEARCH_MAX);
  });

  it("DEC-110 a new history entry (a fresh visit from the sidebar) starts with an empty search", () => {
    writeSearch("/inbox", WORDS);
    window.history.pushState(null, "", "/inbox");
    expect(readSearch("/inbox")).toBe("");
  });

  it("DEC-110 with the Navigation API, the words survive the router writing the entry's state afresh", () => {
    navigation([{ key: "k1", index: 0, url: "http://localhost:3000/desk?tab=waiting&sort=time_left" }], 0);
    writeSearch("/desk", WORDS);
    window.history.replaceState({ __NA: true }, "", window.location.href); // what router.replace and refresh do
    expect(readSearch("/desk")).toBe(WORDS);
    const kept = JSON.parse(window.sessionStorage.getItem("kfin.search")!) as Record<string, { q: string }>;
    expect(Object.keys(kept)).toEqual(["/desk k1"]);
  });

  it("DEC-110 J-BROWSE/6: a page opened afresh onto an entry's slot does not take the words kept there before it", () => {
    vi.spyOn(Date, "now").mockReturnValue(performance.timeOrigin - 60_000);
    navigation([{ key: "k1", index: 0, url: "http://localhost:3000/my-ideas" }], 0, {
      key: "k1",
      type: "replace",
    });
    writeSearch("/my-ideas", WORDS);
    window.history.replaceState(null, "", "/my-ideas"); // a new page: its entry's state starts empty
    expect(readSearch("/my-ideas")).toBe("");
    // a reload of the same page keeps them
    navigation([{ key: "k1", index: 0, url: "http://localhost:3000/my-ideas" }], 0, {
      key: "k1",
      type: "reload",
    });
    expect(readSearch("/my-ideas")).toBe(WORDS);
  });

  it("DEC-110 keeps at most 24 entries' words, newest first, and never writes localStorage or a cookie", () => {
    const nav = navigation([{ key: "k0", index: 0, url: "http://localhost:3000/inbox" }], 0);
    for (let i = 0; i < 30; i++) {
      vi.spyOn(Date, "now").mockReturnValue(1_800_000_000_000 + i);
      nav.currentEntry = { key: `k${i}`, index: 0, url: "http://localhost:3000/inbox" };
      writeSearch("/inbox", `${WORDS} ${i}`);
    }
    const kept = JSON.parse(window.sessionStorage.getItem("kfin.search")!) as Record<string, unknown>;
    expect(Object.keys(kept)).toHaveLength(24);
    expect(kept["/inbox k29"]).toBeDefined();
    expect(kept["/inbox k0"]).toBeUndefined();
    expect(window.localStorage.length).toBe(0);
    expect(document.cookie).toBe("");
  });
});

describe("DEC-110: addresses never hold the words", () => {
  it("DEC-110 replaceAddress keeps the entry's own state, drops the router's keys and any q", () => {
    window.history.replaceState({ __NA: true, __PRIVATE_NEXTJS_INTERNALS_TREE: {}, mine: 1 }, "", "/desk");
    writeSearch("/desk", WORDS);
    replaceAddress(`/desk?tab=decided&sort=area&q=${encodeURIComponent(WORDS)}`);
    expect(window.location.pathname + window.location.search).toBe("/desk?tab=decided&sort=area");
    const state = window.history.state as Record<string, unknown>;
    expect(state.mine).toBe(1);
    expect(state.__NA).toBeUndefined();
    expect(readSearch("/desk")).toBe(WORDS);
  });

  it("DEC-110 cleanAddress takes an older ?q= out of the address without taking its words", () => {
    window.history.replaceState(null, "", "/inbox?tab=all&q=Zebra7Kestrel#top");
    cleanAddress();
    expect(window.location.pathname + window.location.search + window.location.hash).toBe(
      "/inbox?tab=all#top",
    );
    expect(readSearch("/inbox")).toBe("");
  });

  it("DEC-110 withoutSearch and sign-in's next= drop q and keep everything else", () => {
    expect(withoutSearch("/my-ideas?sort=shared&q=Zebra7Kestrel&row=IDEA-2026-000002")).toBe(
      "/my-ideas?sort=shared&row=IDEA-2026-000002",
    );
    expect(withoutSearch("/my-ideas?q=x")).toBe("/my-ideas");
    expect(withoutSearch("/wall?sort=popular#a1")).toBe("/wall?sort=popular#a1");
    expect(withoutSearch("/desk")).toBe("/desk");
    expect(nextParam("/desk", "?tab=waiting&q=Zebra7Kestrel")).toBe(encodeURIComponent("/desk?tab=waiting"));
    expect(nextParam("/ideas/IDEA-2026-000002", "")).toBe("%2Fideas%2FIDEA-2026-000002");
  });

  it("DEC-110 listOf: My ideas, the desk and the Inbox, an item's own Inbox address included", () => {
    expect(listOf("/my-ideas")).toBe("/my-ideas");
    expect(listOf("/inbox/41")).toBe("/inbox");
    expect(listOf("/desk")).toBe("/desk");
    expect(listOf("/desk/ideas/IDEA-2026-000002")).toBe("/desk");
    expect(listOf("/my-ideasx")).toBeNull();
    expect(listOf("/wall")).toBeNull();
  });
});

describe("J-BROWSE/3, DEC-110: the page's own Back link brings the search back", () => {
  const LIST_URL = "http://localhost:3000/my-ideas?sort=shared&row=IDEA-2026-000002&dy=140";
  const IDEA_URL = "http://localhost:3000/ideas/IDEA-2026-000002";

  it("J-BROWSE/3 goes back in history when the entry before is that list and it holds a search", () => {
    const back = vi.spyOn(window.history, "back").mockImplementation(() => undefined);
    const nav = navigation(
      [
        { key: "list", index: 0, url: LIST_URL },
        { key: "idea", index: 1, url: IDEA_URL },
      ],
      0,
    );
    writeSearch("/my-ideas", WORDS); // kept on the list's entry
    nav.currentEntry = nav.entries()[1]!;
    nav.canGoBack = true;
    expect(backToSearchedList("/my-ideas?sort=shared&row=IDEA-2026-000002")).toBe(true);
    expect(back).toHaveBeenCalledOnce();
  });

  it("J-BROWSE/3 opens the link as before when the list there holds no search, or another page is before this one", () => {
    const back = vi.spyOn(window.history, "back").mockImplementation(() => undefined);
    navigation(
      [
        { key: "list", index: 0, url: LIST_URL },
        { key: "idea", index: 1, url: IDEA_URL },
      ],
      1,
    );
    expect(backToSearchedList("/my-ideas?sort=shared")).toBe(false);
    navigation(
      [
        { key: "wall", index: 0, url: "http://localhost:3000/wall" },
        { key: "idea", index: 1, url: IDEA_URL },
      ],
      1,
    );
    expect(backToSearchedList("/wall")).toBe(false);
    delete (window as { navigation?: unknown }).navigation;
    expect(backToSearchedList("/my-ideas")).toBe(false);
    expect(back).not.toHaveBeenCalled();
  });
});
