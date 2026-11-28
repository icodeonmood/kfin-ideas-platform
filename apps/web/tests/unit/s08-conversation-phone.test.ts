// @vitest-environment jsdom
/**
 * S-08 polish (lane F): the phone bar's title (PhoneMessages.md), the box pinned on a phone (S-08.rules/4, BLD-F068:
 * the pin's measurements, the grip-free box that grows with its words) and "Say hello" landing with the cursor in the
 * box (L-TEAMUP.rules/9, BLD-F069: `#say-hello` focuses the box only when the person can write here, at the end of any
 * words carried over from the edit page, and the hint comes off the address either way; nothing is sent). The look
 * pass from lane D's QA (BLD-F078 to F081): the phone's one-row box and the line under the title, the desktop header
 * and solid box, and opening at the newest entry. Synthetic people only: the pack's fictional cast.
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
const { PIN_GAP, SAY_HELLO, grow, keyboardInset, newestTop, pinMetrics } =
  await import("@/components/convo/pin");
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

/** The screen's stylesheet without comments, and the rules inside `@media (max-width: 640px)` on their own. */
function sheet(): { all: string; phone: string; wide: string } {
  const all = readFileSync(
    path.resolve(__dirname, "../../src/components/convo/conversation.css"),
    "utf8",
  ).replace(/\/\*[\s\S]*?\*\//g, "");
  const at = all.indexOf("@media (max-width: 640px)");
  const end = all.indexOf("@media (prefers-reduced-motion", at);
  return { all, phone: all.slice(at, end), wide: all.slice(0, at) };
}

/** The body of the first rule for `selector` in `css`. */
function rule(css: string, selector: string): string {
  const esc = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(?:^|[}\\s])${esc} \\{([^}]*)\\}`).exec(css)?.[1] ?? "";
}

/** The name a screen reader hears: aria-label, else the words less anything aria-hidden. */
function nameOf(el: Element): string {
  const label = el.getAttribute("aria-label");
  if (label) return label;
  const copy = el.cloneNode(true) as Element;
  copy.querySelectorAll('[aria-hidden="true"]').forEach((x) => x.remove());
  return (copy.textContent ?? "").trim();
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

  it("BLD-F068: the room and the scroll margin are kept only while there is a box; a merged idea's closing line keeps none", async () => {
    await arrive(PAGE);
    expect(host.querySelector(".cv")?.getAttribute("data-box")).toBe("open");
    const css = readFileSync(
      path.resolve(__dirname, "../../src/components/convo/conversation.css"),
      "utf8",
    ).replace(/\/\*[\s\S]*?\*\//g, "");
    // every rule that uses the measured room or cover is scoped to an open box
    const users = [...css.matchAll(/([^{}]+)\{[^}]*var\(--cv-(?:room|cover)[^}]*\}/g)].map((m) =>
      m[1]!.trim(),
    );
    expect(users.length).toBeGreaterThanOrEqual(2);
    for (const selectors of users) {
      for (const sel of selectors.split(",")) expect(sel.trim()).toMatch(/^\.cv\[data-box="open"\] /);
    }
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

  it("with words carried over from the edit page (S-06B.rules/2, BLD-C165): the words wait in the box, the cursor is at their end, and nothing is sent", async () => {
    const key = `1pc.conversation.prefill.${IDEA}`;
    const words = "How often: About 50 calls a day at one branch";
    window.sessionStorage.setItem(key, words);
    try {
      await arrive(`${PAGE}${SAY_HELLO}`);
      const el = box()!;
      expect(el.value).toBe(words);
      expect(document.activeElement).toBe(el);
      expect([el.selectionStart, el.selectionEnd]).toEqual([words.length, words.length]);
      expect(fetch).not.toHaveBeenCalled(); // neither arrival sends anything
      expect(window.sessionStorage.getItem(key)).toBeNull();
      expect(window.location.hash).toBe("");
    } finally {
      window.sessionStorage.clear();
    }
  });

  it("carried words without the hint: they wait in the box and focus stays where it was", async () => {
    const key = `1pc.conversation.prefill.${IDEA}`;
    window.sessionStorage.setItem(key, "How often: About 50 calls a day at one branch");
    try {
      await arrive(PAGE);
      expect(box()!.value).toBe("How often: About 50 calls a day at one branch");
      expect(document.activeElement).toBe(before);
      expect(fetch).not.toHaveBeenCalled();
    } finally {
      window.sessionStorage.clear();
    }
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
    expect(host.querySelector(".cv")?.getAttribute("data-box")).toBe("closed"); // no room kept under it (BLD-F068)
    expect(document.activeElement).toBe(before);
    expect(window.location.hash).toBe("");
  });
});

describe("The look pass from lane D's QA (BLD-F078 to F081)", () => {
  it("BLD-F078 PhoneMessages: the box is one grid row with the words, then Send; Send is named “Send” and carries an arrow; no attach control", async () => {
    await arrive(PAGE);
    const form = host.querySelector("form.cv-box")!;
    const row = form.querySelector(".cv-row")!;
    expect(row.querySelector(".cv-field textarea")).toBe(box());
    const send = row.querySelector<HTMLButtonElement>("button.cv-send")!;
    expect(send.getAttribute("type")).toBe("submit");
    expect(nameOf(send)).toBe("Send");
    expect(send.querySelector("svg.cv-send-ic")?.getAttribute("aria-hidden")).toBe("true");
    // The crew may not attach (BLD-F063): no "+" and no empty slot (the sharer's: s08-conversation-attach, BLD-F095).
    expect(form.querySelectorAll("button")).toHaveLength(1);
    expect(form.textContent).not.toContain("Attach");
  });

  it("BLD-F078 PhoneMessages: on a phone (and from the server) who sees the conversation is under the title with the faces, and drawn once; the box is described by it", async () => {
    await arrive(PAGE); // jsdom has no matchMedia: the server's phone layout
    const line = "The crew and the review desk see this conversation.";
    const seen = host.querySelector("header .cv-seen")!;
    expect(seen.textContent).toContain(line);
    const faces = seen.querySelector(".cv-faces")!;
    expect(faces.getAttribute("aria-hidden")).toBe("true"); // the names are in "In this conversation"
    expect([...faces.querySelectorAll(".av")].map((a) => a.textContent)).toEqual(["RN", "KM"]);
    expect(host.querySelector("form .cv-sees")).toBeNull();
    const who = document.getElementById(box()!.getAttribute("aria-describedby")!)!;
    expect(who.closest("header")).not.toBeNull();
    expect(who.textContent).toBe(line);
    expect(host.textContent!.split(line)).toHaveLength(2); // once on the page (lane G's journeys find it by its words)
  });

  it("BLD-F078 Messages.jpg: wider than a phone the line is in the box beside Send, drawn once, and moves when the width crosses 640px", async () => {
    const changed = new Set<() => void>();
    let matches = false;
    vi.stubGlobal(
      "matchMedia",
      vi.fn((q: string) => ({
        get matches() {
          return q === "(max-width: 640px)" ? matches : false;
        },
        media: q,
        addEventListener: (_: string, cb: () => void) => changed.add(cb),
        removeEventListener: (_: string, cb: () => void) => changed.delete(cb),
      })),
    );
    await arrive(PAGE);
    const line = "The crew and the review desk see this conversation.";
    expect(host.querySelector("header .cv-seen")).toBeNull();
    const sees = host.querySelector("form .cv-row > .cv-sees")!;
    expect(sees.textContent).toBe(line);
    expect(box()!.getAttribute("aria-describedby")).toBe(sees.id);
    expect(host.textContent!.split(line)).toHaveLength(2);
    // Narrowed to a phone: the line goes under the title
    matches = true;
    await act(async () => changed.forEach((cb) => cb()));
    expect(host.querySelector("form .cv-sees")).toBeNull();
    expect(host.querySelector("header .cv-seen")?.textContent).toContain(line);
    expect(
      document.getElementById(box()!.getAttribute("aria-describedby")!)?.closest("header"),
    ).not.toBeNull();
    expect(host.textContent!.split(line)).toHaveLength(2);
  });

  it("BLD-F078 at 640px and narrower: one row of the pill and a round 44px Send (no empty attach slot where the reader may not attach, BLD-F063), any error above it; the line in the box gives way to the header's", () => {
    const { phone, wide } = sheet();
    const row = rule(phone, ".cv-row");
    expect(row).toMatch(/grid-template-columns: minmax\(0, 1fr\) 44px;/);
    expect(row.replace(/\s+/g, " ")).toMatch(/grid-template-areas: "err err" "field send";/);
    expect(row).toMatch(/align-items: end;/); // Send stays on the row's bottom edge as the pill grows
    const send = rule(phone, ".cv-box .cv-send");
    expect(send).toMatch(/width: 44px;/);
    expect(send).toMatch(/height: 44px;/);
    expect(send).toMatch(/border-radius: 50%;/);
    expect(rule(phone, ".cv-send .cv-send-t")).toMatch(/clip-path: inset\(50%\);/); // the name stays, out of sight
    expect(rule(phone, ".cv-sees")).toMatch(/display: none;/);
    expect(rule(phone, ".cv-seen")).toMatch(/display: flex;/);
    expect(rule(wide, ".cv-seen")).toMatch(/display: none;/);
    expect(rule(wide, ".cv-send-ic")).toMatch(/display: none;/);
    expect(rule(phone, ".cv-field")).toMatch(/border-radius: 22px;/); // the pill
    expect(rule(phone, ".cv-in")).toMatch(/min-height: 44px;/);
    // The dock: 12px above the row; at the very bottom at least 30px under it, above a bar or the keyboard 12px
    expect(rule(phone, ".cv-box")).toMatch(
      /padding: 12px max\(12px, env\(safe-area-inset-right, 0px\)\)\s+max\(12px, calc\(max\(30px, env\(safe-area-inset-bottom, 0px\) \+ 12px\) \* var\(--cv-safe, 1\)\)\)/,
    );
  });

  it("BLD-F078 Send while sending: busy, named “Sending”, and the arrow gives way to the spinner", async () => {
    let answer: (r: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((r) => (answer = r))),
    );
    await arrive(PAGE);
    const el = box()!;
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
      setter.call(el, "Thanks for the call list.");
      el.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const send = host.querySelector<HTMLButtonElement>("button.cv-send")!;
    await act(async () => send.click());
    expect(send.getAttribute("aria-busy")).toBe("true");
    expect(nameOf(send)).toBe("Sending");
    expect(send.querySelector('.btn-lbl:not([aria-hidden="true"]) .spin')).not.toBeNull();
    await act(async () => answer(new Response(null, { status: 500 })));
  });

  it("BLD-F080 wider than a phone: the sticky box is solid white, and a page-colour band under it reaches past the window's edge", () => {
    const { wide, phone } = sheet();
    const css = rule(wide, ".cv-box");
    expect(css).toMatch(/background: var\(--white\);/);
    expect(css).not.toMatch(/rgba\(255, 255, 255, 0\.\d+\)/);
    expect(css).not.toMatch(/backdrop-filter/);
    const edge = Number(/bottom: (\d+)px;/.exec(css)?.[1]);
    const band = /--cv-band: 0 (\d+)px 0 (\d+)px var\(--paper\);/.exec(css);
    expect(band).not.toBeNull();
    // The band is the box's own shape moved down and widened: its bottom (offset + spread) passes the 20px gap
    expect(Number(band![1]) + Number(band![2])).toBeGreaterThan(edge);
    for (const sel of [".cv-box", ".cv-box:focus-within"]) {
      // the band is the last shadow, so it is painted under the box and its other shadows
      expect(/box-shadow:([^;]*);/.exec(rule(wide, sel))?.[1]?.trim().endsWith("var(--cv-band)"), sel).toBe(
        true,
      );
    }
    expect(rule(phone, ".cv-box")).toMatch(/box-shadow: none;/); // a phone's box is the dock, with no band
  });

  it("BLD-F106 at 640px and narrower: the picker in the dock is solid white, so the thread never shows through it; wider, lane D's shared look stays", () => {
    const { phone, wide } = sheet();
    const pick = rule(phone, ".cv-box .cv-pick");
    expect(pick).toMatch(/background: var\(--white\);/);
    expect(pick).not.toMatch(/var\(--card\)/); // --card is 78% glass inside the signed-in shell
    expect(rule(wide, ".cv-pick")).not.toMatch(/background/); // wider, only its place; `.fpick` draws it
  });

  it("BLD-F079 Messages.jpg: the pill, the reference and the line are one row; the title runs the column's width", async () => {
    await arrive(PAGE);
    const meta = host.querySelector("header .cv-meta")!;
    expect(meta.querySelector(".pill")).not.toBeNull();
    expect(meta.textContent).toContain(IDEA);
    expect(meta.querySelector(".cv-line")?.textContent).toBe("Ravi Nair’s idea, Investor service, Hyderabad");
    const { wide } = sheet();
    expect(rule(wide, ".cv-title")).toMatch(/max-width: min\(780px, calc\(100% - var\(--cv-side\)\)\);/);
    expect(rule(wide, ".cv-title")).toMatch(/--cv-side: 368px;/); // the 320px panel and the 48px gap
  });

  it("BLD-F081 newestTop: the end of the page, never past the newest entry's top; nothing when the page fits", () => {
    // A short newest entry: the end, so it sits just above the box
    expect(newestTop({ page: 2400, viewport: 800, entryTop: 2100, margin: 96 })).toBe(1600);
    // A tall one (the questions card): its top, under the phone's bar
    expect(newestTop({ page: 2400, viewport: 800, entryTop: 1200, margin: 96 })).toBe(1104);
    // The page fits the window
    expect(newestTop({ page: 800, viewport: 812, entryTop: 600, margin: 96 })).toBeNull();
    expect(newestTop({ page: 812, viewport: 812, entryTop: 600, margin: 96 })).toBeNull();
    // Never above the top of the page
    expect(newestTop({ page: 2400, viewport: 800, entryTop: 40, margin: 96 })).toBe(0);
  });

  describe("BLD-F081 the screen opens at its newest entry", () => {
    let scrollTo: ReturnType<typeof vi.fn>;
    let rect: ReturnType<typeof vi.spyOn>;
    beforeEach(() => {
      scrollTo = vi.fn();
      vi.stubGlobal("scrollTo", scrollTo);
      Object.defineProperty(document.documentElement, "scrollHeight", { configurable: true, value: 2400 });
      Object.defineProperty(window, "innerHeight", { configurable: true, value: 800 });
      rect = vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
        top: 2100,
        bottom: 2160,
        left: 0,
        right: 0,
        width: 0,
        height: 60,
        x: 0,
        y: 2100,
        toJSON: () => ({}),
      } as DOMRect);
    });
    afterEach(() => {
      rect.mockRestore();
      delete (document.documentElement as { scrollHeight?: number }).scrollHeight;
      Object.defineProperty(window, "innerHeight", { configurable: true, value: 768 });
      Object.defineProperty(window, "scrollY", { configurable: true, value: 0 });
    });

    it("a long conversation opens at its end, at once, and focus stays where it was", async () => {
      await arrive(PAGE);
      expect(scrollTo).toHaveBeenCalledTimes(1);
      expect(scrollTo).toHaveBeenCalledWith({ top: 1600, left: 0, behavior: "instant" });
      expect(document.activeElement).toBe(before);
    });

    it("with #say-hello as well: the end, and the cursor in the box (BLD-F069)", async () => {
      await arrive(`${PAGE}${SAY_HELLO}`);
      expect(scrollTo).toHaveBeenCalledWith({ top: 1600, left: 0, behavior: "instant" });
      expect(document.activeElement).toBe(box());
    });

    it("a link to one entry goes there, not to the end", async () => {
      await arrive(`${PAGE}#entry-e-approved`);
      expect(scrollTo).not.toHaveBeenCalled();
    });

    it("a page the browser has already scrolled (Back, a reload) stays where the person was", async () => {
      Object.defineProperty(window, "scrollY", { configurable: true, value: 300 });
      await arrive(PAGE);
      expect(scrollTo).not.toHaveBeenCalled();
    });
  });
});
