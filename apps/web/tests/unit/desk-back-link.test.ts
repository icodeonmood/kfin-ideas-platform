// @vitest-environment jsdom
/**
 * S-R2.layout, J-BROWSE/3 and /4 (BLD-B260): S-R2's own "Review desk" link goes back in history whenever the entry
 * before it is the review desk, searched or not, so the reviewer's tab, sort and row come back as they were. Any other
 * page before it, the first entry, or no Navigation API: the plain /desk link. Lane A's `backToSearchedList` keeps its
 * own rule for S-06 and S-09 (a list without a search opens the link). Synthetic data only.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { backToList, backToSearchedList, writeSearch } from "@/lib/search-memory";

type Entry = { key: string; index: number; url: string };
const ORIGIN = "http://localhost:3000";
const DESK = `${ORIGIN}/desk?tab=asked&sort=oldest&row=IDEA-2026-001481`;
const IDEA = `${ORIGIN}/desk/ideas/IDEA-2026-001481`;

function navigation(entries: Entry[], at: number) {
  const nav = { currentEntry: entries[at]!, canGoBack: at > 0, entries: () => entries };
  Object.defineProperty(window, "navigation", { value: nav, configurable: true, writable: true });
  return nav;
}

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
  Object.defineProperty(window, "sessionStorage", {
    value: memoryStorage(),
    configurable: true,
    writable: true,
  });
  window.history.replaceState(null, "", "/desk/ideas/IDEA-2026-001481");
});
afterEach(() => {
  delete (window as { navigation?: unknown }).navigation;
  vi.restoreAllMocks();
});

describe("S-R2's Back link to the review desk (J-BROWSE/3, /4)", () => {
  it("J-BROWSE/3, S-R2.layout: goes back when the desk without a search is the entry before, where backToSearchedList would not", () => {
    const back = vi.spyOn(window.history, "back").mockImplementation(() => undefined);
    navigation(
      [
        { key: "desk", index: 0, url: DESK },
        { key: "idea", index: 1, url: IDEA },
      ],
      1,
    );
    expect(backToSearchedList("/desk")).toBe(false); // lane A's rule for S-06 and S-09 is unchanged
    expect(back).not.toHaveBeenCalled();
    expect(backToList("/desk")).toBe(true);
    expect(back).toHaveBeenCalledOnce();
  });

  it("J-BROWSE/4: goes back when the desk before it holds a search, as before", () => {
    const back = vi.spyOn(window.history, "back").mockImplementation(() => undefined);
    const nav = navigation([{ key: "desk", index: 0, url: DESK }], 0);
    writeSearch("/desk", "Zebra7Kestrel redemption"); // kept on the desk's entry
    nav.currentEntry = { key: "idea", index: 1, url: IDEA };
    nav.entries = () => [
      { key: "desk", index: 0, url: DESK },
      { key: "idea", index: 1, url: IDEA },
    ];
    nav.canGoBack = true;
    expect(backToList("/desk")).toBe(true);
    expect(back).toHaveBeenCalledOnce();
  });

  it("S-R2.layout: the plain link when another page, another idea or nothing is before it, or there is no Navigation API", () => {
    const back = vi.spyOn(window.history, "back").mockImplementation(() => undefined);
    for (const before of [
      `${ORIGIN}/inbox`,
      `${ORIGIN}/desk/ideas/IDEA-2026-001412`, // another idea on the desk is not the desk
      "https://elsewhere.example/desk",
    ]) {
      navigation(
        [
          { key: "before", index: 0, url: before },
          { key: "idea", index: 1, url: IDEA },
        ],
        1,
      );
      expect(backToList("/desk")).toBe(false);
    }
    navigation([{ key: "idea", index: 0, url: IDEA }], 0); // opened from a pasted link: the first entry
    expect(backToList("/desk")).toBe(false);
    delete (window as { navigation?: unknown }).navigation;
    expect(backToList("/desk")).toBe(false);
    expect(back).not.toHaveBeenCalled();
  });
});
