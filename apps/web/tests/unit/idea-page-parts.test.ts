// @vitest-environment jsdom
/**
 * The idea page's client parts (BLD-E044). The way back (P-ROUTES.state, BLD-E021) is kept per history entry and keyed
 * on the page's own route, never on window.location, so moving from one idea to another without `from` and `back` (a
 * similar-idea tile) never carries the first idea's way back over; only a way back to the Wall or My ideas, as the
 * worker's `safe_back` allows, or to a joined idea's lead (`back_link`, S-09.layout/1) is ever restored. The phone's
 * reference copies itself as PhoneStatus.md draws it.
 * Synthetic references only.
 */
import { act, createElement, Fragment, useInsertionEffect, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const route = vi.hoisted(() => ({ id: "IDEA-2026-001481" }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: route.id }) }));

import {
  allowedBack,
  COPY_REF,
  CopyRef,
  useWay,
  WayBack,
  type Carried,
  type Way,
} from "@/app/ideas/[id]/parts";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const A = "IDEA-2026-001481";
const B = "IDEA-2026-001412";
const WALL: Way = { label: "Back to the Wall", to: "/wall" };
const WALL_BY_CREW: Way = { label: "Back to the Wall", to: "/wall?sort=crew" };
const NEEDS_YOU: Way = { label: "My ideas, Needs you", to: "/my-ideas?filter=needs_you" };

type Kept = { ipWayBack?: { path: string; way: Way } } | null;
const kept = () => (window.history.state as Kept)?.ipWayBack;

/** Stands in for Next's HistoryUpdater: the new entry is pushed in an insertion effect, so while the next idea first
 * renders, the address and the history state are still the previous idea's. */
function Pushes({ to }: { to: string }) {
  useInsertionEffect(() => {
    window.history.pushState({ __NA: true }, "", to);
  }, [to]);
  return null;
}

function Shown() {
  const way = useWay({ label: "unset", to: "/unset" });
  return createElement("a", { id: "way", href: way.to }, way.label);
}

function shown(): Way {
  const a = document.getElementById("way") as HTMLAnchorElement;
  return { label: a.textContent ?? "", to: a.getAttribute("href") ?? "" };
}

let host: HTMLDivElement;
let root: Root | null = null;

function open(id: string, way: Way, carried: Carried, push?: string) {
  route.id = id;
  root?.unmount();
  root = createRoot(host);
  const page = createElement(
    WayBack,
    { way, carried } as Parameters<typeof WayBack>[0],
    createElement(Shown),
  );
  act(() => {
    root!.render(push ? createElement(Fragment, null, createElement(Pushes, { to: push }), page) : page);
  });
}

beforeEach(() => {
  window.history.replaceState(null, "", "/");
  host = document.createElement("div");
  document.body.append(host);
});

afterEach(() => {
  act(() => root?.unmount());
  root = null;
  host.remove();
});

describe("BLD-E044: the way back follows the idea on screen, not the address", () => {
  it("A with a kept way back, then B with no from or back: B shows its own default, and keeps it on a reload", () => {
    // Idea A, opened from the Wall sorted by crew size, after its address was cleaned
    window.history.replaceState(
      { __NA: true, ipWayBack: { path: `/ideas/${A}`, way: WALL_BY_CREW } },
      "",
      `/ideas/${A}`,
    );
    open(A, WALL, null);
    expect(shown()).toEqual(WALL_BY_CREW);

    // A similar-idea tile to B: no from or back, so the server draws B's default way back
    open(B, WALL, null, `/ideas/${B}`);
    expect(window.location.pathname).toBe(`/ideas/${B}`);
    expect(shown()).toEqual(WALL);
    expect(kept()).toBeUndefined();

    // A reload of B still has nothing kept
    open(B, WALL, null);
    expect(shown()).toEqual(WALL);
    expect(kept()).toBeUndefined();
  });

  it("A, then B from My ideas' Needs you: B keeps its own way back, keyed on B", () => {
    window.history.replaceState(
      { __NA: true, ipWayBack: { path: `/ideas/${A}`, way: WALL_BY_CREW } },
      "",
      `/ideas/${A}`,
    );
    open(A, WALL, null);
    open(B, NEEDS_YOU, "keep", `/ideas/${B}?from=my-ideas&back=${encodeURIComponent(NEEDS_YOU.to)}`);
    expect(shown()).toEqual(NEEDS_YOU);
    expect(window.location.pathname + window.location.search).toBe(`/ideas/${B}`);
    expect(kept()).toEqual({ path: `/ideas/${B}`, way: NEEDS_YOU });
  });

  it("a reload of the clean address takes the way back this entry kept", () => {
    window.history.replaceState(
      { __NA: true, ipWayBack: { path: `/ideas/${B}`, way: NEEDS_YOU } },
      "",
      `/ideas/${B}`,
    );
    open(B, { label: "My ideas", to: "/my-ideas" }, null);
    expect(shown()).toEqual(NEEDS_YOU);
  });

  it("from and back leave the address and the way back is kept for a reload", () => {
    window.history.replaceState(
      { __NA: true },
      "",
      `/ideas/${B}?from=wall&back=${encodeURIComponent(WALL_BY_CREW.to)}`,
    );
    open(B, WALL_BY_CREW, "keep");
    expect(window.location.pathname + window.location.search).toBe(`/ideas/${B}`);
    expect(kept()).toEqual({ path: `/ideas/${B}`, way: WALL_BY_CREW });

    open(B, WALL, null);
    expect(shown()).toEqual(WALL_BY_CREW);
  });

  it("S-09.layout/1: a joined idea opened from its lead keeps the way back to the lead for a reload", () => {
    const LEAD: Way = { label: `Back to ${A}`, to: `/ideas/${A}` };
    window.history.replaceState({ __NA: true }, "", `/ideas/${B}?from=${A}`);
    open(B, LEAD, "keep");
    expect(window.location.pathname + window.location.search).toBe(`/ideas/${B}`);
    expect(kept()).toEqual({ path: `/ideas/${B}`, way: LEAD });

    open(B, WALL, null);
    expect(shown()).toEqual(LEAD);
  });

  it("from=share holds Home for the visit and is never kept (S-06.rules/6)", () => {
    window.history.replaceState({ __NA: true }, "", `/ideas/${B}?from=share`);
    open(B, { label: "Home", to: "/home" }, "once");
    expect(shown()).toEqual({ label: "Home", to: "/home" });
    expect(window.location.search).toBe("");
    expect(kept()).toBeUndefined();

    open(B, { label: "My ideas", to: "/my-ideas" }, null);
    expect(shown()).toEqual({ label: "My ideas", to: "/my-ideas" });
  });
});

describe("BLD-E044, S-09.layout/1: only a way back to the Wall, My ideas or a lead idea is restored, as the worker allows", () => {
  it.each([
    "/wall",
    "/wall?sort=crew",
    "/wall/ones",
    "/my-ideas",
    "/my-ideas?filter=needs_you",
    "/my-ideas/drafts",
    "/ideas/IDEA-2026-001481",
  ])("accepts %s", (to) => {
    expect(allowedBack(to)).toBe(true);
  });

  it.each([
    "//wall",
    "//evil.example/wall",
    "/\\evil.example",
    "/wall\\..\\evil",
    "/\t/evil.example",
    "/wall\n",
    "https://evil.example/wall",
    "wall",
    "/wallet",
    "/my-ideasx",
    "/home",
    "/ideas/IDEA-2026-00148",
    "/ideas/IDEA-2026-001481/x",
    "/ideas/IDEA-2026-001481?from=wall",
    "/ideas/IDEA-2026-001481#top",
    "/ideas/IDEA-26-001481",
    "/ideas/foo",
    "/ideas",
    "//ideas/IDEA-2026-001481",
    "/ideas/IDEA-2026-001481\n",
    "",
  ])("rejects %j", (to) => {
    expect(allowedBack(to)).toBe(false);
  });

  it("rejects a way back longer than the worker takes (600 characters)", () => {
    expect(allowedBack(`/wall?q=${"q".repeat(600)}`)).toBe(false);
  });

  it("a kept way back to anywhere else is ignored and the default shows", () => {
    for (const to of ["//evil.example/wall", "/\\evil.example", "/home", "https://evil.example/wall"]) {
      window.history.replaceState(
        { __NA: true, ipWayBack: { path: `/ideas/${B}`, way: { label: "Back to the Wall", to } } },
        "",
        `/ideas/${B}`,
      );
      open(B, WALL, null);
      expect(shown()).toEqual(WALL);
    }
  });
});

describe("S-06, PhoneStatus.md: Copy reference", () => {
  const REF = "IDEA-2026-001481";

  function Page() {
    const [said, setSaid] = useState("");
    return createElement(
      Fragment,
      null,
      createElement(CopyRef, { value: REF, say: setSaid }),
      createElement("p", { id: "said", role: "status" }, said),
    );
  }

  const button = () => host.querySelector("button") as HTMLButtonElement;
  const said = () => document.getElementById("said")?.textContent ?? "";
  const clipboard = (writeText: ((t: string) => Promise<void>) | null) =>
    Object.defineProperty(navigator, "clipboard", {
      value: writeText ? { writeText } : undefined,
      configurable: true,
    });

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    root = createRoot(host);
    act(() => root!.render(createElement(Page)));
  });

  afterEach(() => {
    vi.useRealTimers();
    clipboard(null);
  });

  it("copied: the button is named Reference copied and the line says which reference, then both go back", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    clipboard(writeText);
    expect(button().getAttribute("aria-label")).toBe(`Copy reference ${REF}`);

    await act(async () => button().click());
    expect(writeText).toHaveBeenCalledWith(REF);
    expect(button().getAttribute("aria-label")).toBe("Reference copied");
    expect(button().textContent).toBe("Reference copied");
    expect(said()).toBe(`Reference ${REF} copied`);

    act(() => vi.advanceTimersByTime(2_500));
    expect(button().getAttribute("aria-label")).toBe(`Copy reference ${REF}`);
    expect(button().textContent).toBe(REF);
    expect(said()).toBe("");
  });

  it("the browser refuses: the line says so in plain words and the button stays as it was", async () => {
    clipboard(() => Promise.reject(new Error("denied")));
    await act(async () => button().click());
    expect(said()).toBe(COPY_REF.failed(REF));
    expect(said()).toBe(`Couldn't copy the reference. It's ${REF}.`);
    expect(button().getAttribute("aria-label")).toBe(`Copy reference ${REF}`);
  });

  it("no clipboard at all: the same plain line", async () => {
    clipboard(null);
    await act(async () => button().click());
    expect(said()).toBe(COPY_REF.failed(REF));
  });

  it("leaving the page clears the timer", async () => {
    clipboard(() => Promise.resolve());
    await act(async () => button().click());
    expect(vi.getTimerCount()).toBe(1);
    act(() => root?.unmount());
    root = null;
    expect(vi.getTimerCount()).toBe(0);
  });
});
