// @vitest-environment jsdom
/**
 * S-08 polish (lane F): the phone bar's title (PhoneMessages.md), the box pinned on a phone (S-08.rules/4, BLD-F068:
 * the pin's measurements, the grip-free box that grows with its words) and "Say hello" landing with the cursor in the
 * box (L-TEAMUP.rules/9, BLD-F069: `#say-hello` focuses the box only when the person can write here, and the hint
 * comes off the address either way). Synthetic people only: the pack's fictional cast.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));

const { Conversation } = await import("@/components/convo/conversation");
const { PIN_GAP, SAY_HELLO, grow, keyboardInset, pinMetrics } = await import("@/components/convo/pin");
type View = import("@/lib/contracts").ConversationView;

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const IDEA = "IDEA-2026-001412";
const PAGE = `/ideas/${IDEA}/conversation`;
const RAVI = { id: "u-ravi", name: "Ravi Nair", first_name: "Ravi", initials: "RN" };
const KAVYA = { id: "u-kavya", name: "Kavya Menon", first_name: "Kavya", initials: "KM" };

/** Ravi's idea after Kavya teamed up (J-TEAMUP/5–6): where "Say hello" lands. */
function crewView(): View {
  return {
    idea: {
      id: IDEA,
      title: "Rejection SMS codes confuse investors",
      status: "with_review_desk",
      meta: `${IDEA}, with the review desk`,
    },
    audience: "crew_and_desk",
    header: { whose: "The idea", line: "Ravi Nair’s idea, Investor service, Hyderabad" },
    participants: [
      { person: RAVI, label: "Ravi Nair", doing: "Shared the idea", you: false },
      { person: KAVYA, label: "You", doing: "Joined today", you: true },
    ],
    entries: [
      {
        type: "event",
        id: "e-approved",
        code: "teamup.approved_team_only",
        text: "Ravi Nair approved your team-up request. Today, 10:05 am",
        at: "2026-11-17T10:05:00+05:30",
      },
    ],
    composer: {
      placeholder: "Message the crew",
      visibility: "The crew and the review desk see this conversation.",
      can_attach: false,
    },
  } as View;
}

let host: HTMLDivElement;
let root: Root;
let before: HTMLButtonElement;

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  // Something that had focus before the screen arrived (the link that was pressed, say)
  before = document.createElement("button");
  before.textContent = "Before";
  document.body.append(before);
  root = createRoot(host);
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(null, { status: 500 })),
  );
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  before.remove();
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

async function arrive(at: string, view: View = crewView(), paused?: boolean) {
  window.history.replaceState({ router: "kept" }, "", at);
  before.focus();
  await act(async () => {
    root.render(createElement(Conversation, { initial: view, ideaId: IDEA, now: () => 0, paused }));
  });
}

function box(): HTMLTextAreaElement | null {
  return host.querySelector("textarea");
}

describe("S-08 on a phone", () => {
  it("PhoneMessages.md: the compact bar reads Back to the idea and the title “Conversation”, not the idea's title", async () => {
    await arrive(PAGE);
    const bar = host.querySelector(".pnav")!;
    expect(bar.querySelector(".pnav-t")?.textContent).toBe("Conversation");
    expect(bar.querySelector("a")?.getAttribute("href")).toBe(`/ideas/${IDEA}`);
    expect(bar.querySelector("a")?.textContent).toBe("The idea");
  });

  it("S-08.rules/4, BLD-F068: the box has no resize grip; it grows with its words to a max-height, then scrolls", async () => {
    const css = readFileSync(path.resolve(__dirname, "../../src/components/convo/conversation.css"), "utf8");
    const rule = /\.cv-in \{([^}]*)\}/.exec(css)?.[1] ?? "";
    expect(rule).toMatch(/resize: none;/);
    expect(rule).toMatch(/max-height: \d+px;/);
    expect(rule).toMatch(/overflow-y: auto;/);
    expect(css).not.toMatch(/resize: (vertical|both|horizontal)/);

    await arrive(PAGE);
    const el = box()!;
    expect(el.getAttribute("rows")).toBe("1");
    Object.defineProperty(el, "scrollHeight", { configurable: true, value: 96 });
    grow(el);
    expect(el.style.height).toBe("96px");
    Object.defineProperty(el, "scrollHeight", { configurable: true, value: 0 });
    grow(el); // nothing laid out (hidden): CSS decides
    expect(el.style.height).toBe("");
  });

  it("BLD-F068 pinMetrics: above the tab bar, or the keyboard when open; the timeline keeps room past the shell's padding", () => {
    // The kit and main today: a tab bar of 83px, the shell's 96px under the page
    expect(pinMetrics({ fixed: true, box: 130, tabs: 83, keyboard: 0, mainPad: 96 })).toEqual({
      at: 83,
      cover: 213,
      room: 213 - 96 + PIN_GAP,
      safe: 0,
    });
    // A task screen (lane D's shell): no tab bar, 120px under the page; the box takes the safe area
    expect(pinMetrics({ fixed: true, box: 150, tabs: 0, keyboard: 0, mainPad: 120 })).toEqual({
      at: 0,
      cover: 150,
      room: 30 + PIN_GAP,
      safe: 1,
    });
    // The keyboard is open: the box sits on it, over any tab bar
    expect(pinMetrics({ fixed: true, box: 130, tabs: 83, keyboard: 300, mainPad: 96 }).at).toBe(300);
    // A short box under a tall padding still leaves the gap
    expect(pinMetrics({ fixed: true, box: 60, tabs: 0, keyboard: 0, mainPad: 120 }).room).toBe(PIN_GAP);
    // Wider than a phone the box is not fixed: nothing is kept
    expect(pinMetrics({ fixed: false, box: 200, tabs: 0, keyboard: 0, mainPad: 0 })).toEqual({
      at: 0,
      cover: 0,
      room: 0,
      safe: 1,
    });
  });

  it("BLD-F068 keyboardInset: an open keyboard's height; 0 for the browser's own bars, a zoomed page or no API", () => {
    expect(keyboardInset({ height: 400, offsetTop: 0, scale: 1 }, 740)).toBe(340);
    expect(keyboardInset({ height: 400, offsetTop: 40, scale: 1 }, 740)).toBe(300);
    expect(keyboardInset({ height: 684, offsetTop: 0, scale: 1 }, 740)).toBe(0); // a toolbar, not a keyboard
    expect(keyboardInset({ height: 300, offsetTop: 0, scale: 2 }, 740)).toBe(0); // pinch-zoomed
    expect(keyboardInset(null, 740)).toBe(0);
    expect(keyboardInset(undefined, 740)).toBe(0);
  });
});

describe("Say hello lands in the box (L-TEAMUP.rules/9, BLD-F069)", () => {
  it("the hint is #say-hello, with no words in it", () => {
    expect(SAY_HELLO).toBe("#say-hello");
  });

  it("with #say-hello: the cursor is in the box, and the hint comes off the address, keeping the router's state", async () => {
    await arrive(`${PAGE}${SAY_HELLO}`);
    expect(document.activeElement).toBe(box());
    expect(window.location.hash).toBe("");
    expect(window.location.pathname).toBe(PAGE);
    expect(window.history.state).toEqual({ router: "kept" });
  });

  it("the query stays when the hint comes off", async () => {
    await arrive(`${PAGE}?from=inbox${SAY_HELLO}`);
    expect(document.activeElement).toBe(box());
    expect(window.location.search).toBe("?from=inbox");
    expect(window.location.hash).toBe("");
  });

  it("without the hint, or with another hash: focus stays where it was and the address is left alone", async () => {
    await arrive(PAGE);
    expect(document.activeElement).toBe(before);
    act(() => root.unmount());
    root = createRoot(host);
    await arrive(`${PAGE}#entry-e-approved`);
    expect(document.activeElement).toBe(before);
    expect(window.location.hash).toBe("#entry-e-approved");
  });

  it("writing paused by the kill switch (BLD-F058): focus stays where it was; the hint still comes off", async () => {
    await arrive(`${PAGE}${SAY_HELLO}`, crewView(), true);
    expect(box()).not.toBeNull(); // the box stays; only the cursor does not move
    expect(document.activeElement).toBe(before);
    expect(window.location.hash).toBe("");
  });

  it("a conversation that takes no new messages (a merged idea): focus stays where it was; the hint comes off", async () => {
    const v = crewView();
    v.composer = {
      ...v.composer,
      closed: "This idea is now part of another one. Write in IDEA-2026-001481’s conversation.",
    };
    await arrive(`${PAGE}${SAY_HELLO}`, v);
    expect(box()).toBeNull();
    expect(document.activeElement).toBe(before);
    expect(window.location.hash).toBe("");
  });
});
