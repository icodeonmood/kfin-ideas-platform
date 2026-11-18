// @vitest-environment jsdom
/**
 * S-R1, DEC-110 (BLD-A218, BLD-A219; J-BROWSE/4): the review desk's search is never in a URL. The page and the
 * address name the tab and sort; the search stays in this tab's memory of the history entry and goes to the server
 * in a POST body. Back and a reload bring it back before the first read, so the opened row is placed in the searched
 * list; until that read lands the unsearched rows, counts and summary are not shown. Every write to the entry's
 * state merges, so the search survives the row being written for Back. Synthetic people and ideas.
 */
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { NextRequest, NextResponse } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DeskResponse, DeskRow } from "@/lib/contracts";
import { readSearch, writeSearch } from "@/lib/search-memory";

const gate = vi.hoisted(() => ({ allowed: true }));
vi.mock("@/server/auth/authorize", () => ({
  authorize: vi.fn(async () =>
    gate.allowed ? { id: "u-harish" } : NextResponse.json({ error: { code: "forbidden" } }, { status: 403 }),
  ),
  signedIn: vi.fn(async () => ({ id: "u-harish" })),
}));
const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn() }),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));
vi.mock("@/lib/motion/flip", () => ({ useFlipList: () => undefined }));

const { DeskView } = await import("@/app/desk/desk-view");
const route = await import("@/app/api/desk/route");

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const WORDS = "Zebra7Kestrel";

function row(id: string, title: string): DeskRow {
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
const ALL = [
  row("IDEA-2026-000501", "Rejection SMS gives a code"),
  row("IDEA-2026-000502", `${WORDS} branch form`),
];
function desk(items: DeskRow[], summary: string, tab: DeskResponse["tab"] = "waiting"): DeskResponse {
  return {
    items,
    total: items.length,
    counts: { to_review: 0, waiting: items.length, answered: 0, decided: 0 },
    summary,
    tab,
    sort: "time_left",
    waiting_on_sharers: [],
    now: "2026-11-18T10:00:00+05:30",
  };
}

// --- the API route ----------------------------------------------------------------------------------------------

describe("DEC-110, BLD-A219: /api/desk reads a search only from a POST body", () => {
  let calls: { url: URL; init: RequestInit }[];
  const saved = { ...process.env };
  beforeEach(() => {
    process.env.INTERNAL_API_TOKEN = "test-token-for-the-desk-proxy";
    process.env.WORKER_URL = "http://worker.test";
    gate.allowed = true;
    calls = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL, init: RequestInit = {}) => {
        calls.push({ url: new URL(String(input)), init });
        return new Response(JSON.stringify(desk([], "")), { status: 200 });
      }),
    );
  });
  afterEach(() => {
    process.env = { ...saved };
    vi.unstubAllGlobals();
  });

  it("S-R1 GET passes the tab and sort on and never a q", async () => {
    await route.GET(new NextRequest(`http://localhost/api/desk?tab=decided&sort=area&q=${WORDS}`));
    expect(calls[0]!.url.pathname).toBe("/internal/desk");
    expect(Object.fromEntries(calls[0]!.url.searchParams)).toEqual({
      user_id: "u-harish",
      tab: "decided",
      sort: "area",
    });
  });

  it("S-R1 POST passes tab, sort and the search in the worker's POST body, cut at 200; the URL holds only the person", async () => {
    const res = await route.POST(
      new NextRequest("http://localhost/api/desk", {
        method: "POST",
        body: JSON.stringify({ tab: "to_review", sort: "area", q: WORDS, user_id: "someone-else", extra: 1 }),
      }),
    );
    expect(res.status).toBe(200);
    const call = calls[0]!;
    expect(call.init.method).toBe("POST");
    expect(call.url.href).toBe("http://worker.test/internal/desk?user_id=u-harish");
    expect(JSON.parse(String(call.init.body))).toEqual({ tab: "to_review", sort: "area", q: WORDS });
    calls = [];
    await route.POST(
      new NextRequest("http://localhost/api/desk", {
        method: "POST",
        body: JSON.stringify({ q: "a".repeat(250) }),
      }),
    );
    expect((JSON.parse(String(calls[0]!.init.body)) as { q: string }).q).toHaveLength(200);
  });

  it("S-R1 POST meets the same gate as GET: refused before the worker", async () => {
    gate.allowed = false;
    const res = await route.POST(
      new NextRequest("http://localhost/api/desk", { method: "POST", body: JSON.stringify({ q: WORDS }) }),
    );
    expect(res.status).toBe(403);
    expect(calls).toHaveLength(0);
  });
});

// --- the screen -------------------------------------------------------------------------------------------------

describe("DEC-110, S-R1.rules/4, J-BROWSE/4: the desk keeps its search in the tab's memory", () => {
  let host: HTMLDivElement;
  let root: Root;
  let asked: { url: string; init: RequestInit }[];

  beforeEach(() => {
    window.history.replaceState(null, "", "/desk?tab=waiting&sort=time_left");
    asked = [];
    push.mockClear();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit = {}) => {
        asked.push({ url: String(url), init });
        const q = init.body ? (JSON.parse(String(init.body)) as { q: string }).q : "";
        const items = q ? ALL.filter((r) => r.title.includes(q)) : ALL;
        return new Response(
          JSON.stringify(desk(items, q ? "1 waiting on colleagues." : "2 waiting on colleagues.")),
          {
            status: 200,
          },
        );
      }),
    );
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
    vi.unstubAllGlobals();
  });

  async function settle() {
    for (let i = 0; i < 3; i++) {
      await act(async () => await new Promise<void>((r) => requestAnimationFrame(() => r())));
      for (let j = 0; j < 6; j++) await act(async () => await Promise.resolve());
    }
  }
  const here = () => window.location.pathname + window.location.search;
  const box = () => host.querySelector<HTMLInputElement>('input[type="search"]')!;
  const titles = () => [...host.querySelectorAll(".rd-title")].map((a) => a.textContent);

  it("S-R1 DEC-110 a search goes in a POST body and this tab's memory; the address keeps the tab and sort", async () => {
    act(() => root.render(createElement(DeskView, { initial: desk(ALL, "2 waiting on colleagues.") })));
    await settle();
    expect(box().getAttribute("autocomplete")).toBe("off");
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    act(() => {
      set.call(box(), WORDS);
      box().dispatchEvent(new Event("input", { bubbles: true }));
    });
    act(() => {
      box().form!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    await settle();
    const last = asked.at(-1)!;
    expect(last.url).toBe("/api/desk");
    expect(last.init.method).toBe("POST");
    expect(JSON.parse(String(last.init.body))).toEqual({ tab: "waiting", sort: "time_left", q: WORDS });
    expect(titles()).toEqual([`${WORDS} branch form`]);
    expect(here()).toBe("/desk?tab=waiting&sort=time_left");
    expect(readSearch("/desk")).toBe(WORDS);
    expect(asked.map((a) => a.url).join(" ")).not.toContain(WORDS);

    // Opening a row writes the row for Back and keeps the search in the same entry (a merge, never a wipe)
    const link = host.querySelector<HTMLAnchorElement>(".rd-title")!;
    act(() => link.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 })));
    expect(here()).toMatch(/^\/desk\?tab=waiting&sort=time_left&row=IDEA-2026-000502&dy=-?\d+$/);
    expect(readSearch("/desk")).toBe(WORDS);
    expect(push).toHaveBeenCalledWith("/desk/ideas/IDEA-2026-000502");
  });

  it("S-R1 DEC-110 Back or a reload: the kept search is read before the first load; the table and summary wait for it", async () => {
    writeSearch("/desk", WORDS);
    window.history.replaceState(
      window.history.state,
      "",
      "/desk?tab=waiting&sort=time_left&row=IDEA-2026-000502&dy=80",
    );
    act(() => root.render(createElement(DeskView, { initial: desk(ALL, "2 waiting on colleagues.") })));
    // Held: no unsearched rows, counts or summary for a live region to read out
    expect(titles()).toEqual([]);
    expect(host.querySelector(".rd-summary")!.textContent).toBe("");
    expect(host.querySelector('[aria-busy="true"]')).not.toBeNull();
    await settle();
    expect(box().value).toBe(WORDS);
    expect(JSON.parse(String(asked[0]!.init.body))).toEqual({ tab: "waiting", sort: "time_left", q: WORDS });
    expect(titles()).toEqual([`${WORDS} branch form`]);
    expect(host.querySelector(".rd-summary")!.textContent).toBe("1 waiting on colleagues.");
    expect(here()).toBe("/desk?tab=waiting&sort=time_left");
    expect(readSearch("/desk")).toBe(WORDS);
    // the opened row is placed in the searched list, its link focused (J-BROWSE/4)
    expect(document.activeElement?.textContent).toBe(`${WORDS} branch form`);

    // Coming back to the tab reads the list again with the same search
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    await settle();
    expect(JSON.parse(String(asked.at(-1)!.init.body))).toMatchObject({ q: WORDS });
  });

  it("S-R1 DEC-110 the arrival read with the kept search fails: the words stay kept, nothing unsearched shows, Try again reads it", async () => {
    writeSearch("/desk", WORDS);
    const real = globalThis.fetch;
    let down = true;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit = {}) => {
        if (down && init.method === "POST") {
          asked.push({ url: String(url), init });
          throw new TypeError("fetch failed");
        }
        return real(url, init);
      }),
    );
    act(() => root.render(createElement(DeskView, { initial: desk(ALL, "2 waiting on colleagues.") })));
    await settle();
    expect(readSearch("/desk")).toBe(WORDS);
    expect(box().value).toBe(WORDS);
    expect(titles()).toEqual([]);
    expect(host.querySelector(".rd-summary")!.textContent).toBe("");
    expect([...host.querySelectorAll('[role="tab"]')].map((t) => t.textContent)).not.toContain(
      "Waiting on the sharer2",
    );
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("That didn’t go through. Try again.");

    // Coming back to the tab does not read the list without the words meanwhile
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    await settle();
    expect(asked.every((a) => a.init.method === "POST")).toBe(true);
    expect(readSearch("/desk")).toBe(WORDS);

    down = false;
    const again = [...host.querySelectorAll("button")].find((b) => b.textContent === "Try again")!;
    again.focus();
    act(() => again.click());
    // S-R1 (BLD-B262): the button leaves with the failed line, and focus stays on the page: the tab panel has it
    const panel = host.querySelector<HTMLElement>('[role="tabpanel"]')!;
    expect(again.isConnected).toBe(false);
    expect(document.activeElement).toBe(panel);
    expect(panel.getAttribute("aria-busy")).toBe("true");
    await settle();
    expect(document.activeElement).toBe(panel);
    expect(panel.getAttribute("aria-busy")).toBeNull();
    expect(titles()).toEqual([`${WORDS} branch form`]);
    expect(readSearch("/desk")).toBe(WORDS);
    expect(host.querySelector('[role="alert"]')).toBeNull();
  });

  it("S-R1 DEC-110 a visibility re-read or a tab chosen before the arrival frame keeps the kept words", async () => {
    writeSearch("/desk", WORDS);
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    act(() => root.render(createElement(DeskView, { initial: desk(ALL, "2 waiting on colleagues.") })));
    // before the first frame: the box is still empty
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    expect(readSearch("/desk")).toBe(WORDS);
    const tab = [...host.querySelectorAll<HTMLElement>('[role="tab"]')].find((t) =>
      t.textContent?.startsWith("To review"),
    )!;
    act(() => tab.click());
    expect(readSearch("/desk")).toBe(WORDS);
    expect(JSON.parse(String(asked[0]!.init.body))).toMatchObject({ tab: "to_review", q: WORDS });
    await settle();
    expect(box().value).toBe(WORDS);
    expect(readSearch("/desk")).toBe(WORDS);
  });

  it("S-R1 J-BROWSE/6 DEC-110 a fresh visit or a link is read without a search, with GET", async () => {
    window.history.replaceState(null, "", `/desk?tab=waiting&sort=time_left&q=${WORDS}`);
    act(() => root.render(createElement(DeskView, { initial: desk(ALL, "2 waiting on colleagues.") })));
    await settle();
    expect(box().value).toBe("");
    expect(asked[0]!.url).toBe("/api/desk?tab=waiting&sort=time_left");
    expect(here()).toBe("/desk?tab=waiting&sort=time_left");
    expect(titles()).toHaveLength(2);
  });
});
