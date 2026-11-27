// @vitest-environment jsdom
/**
 * C-PHONE-TABS.dock (BLD-D028): on a phone the dock renders through a portal into the shell's slot at the end of
 * `main#main`, so no panel's blur, sheet's transform or arriving block can hold it, and it measures its own height as
 * `--dock-h` on <html> (with `data-dock`), from which the shell keeps room under the page and scrolls a focused field
 * clear of it. On a desk, and without the shell, it stays where the page put it. Synthetic only.
 */
import { act, createElement as h, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { cssRules } from "./helpers/css-rules";

vi.mock("next/navigation", () => ({
  usePathname: () => "/display",
  useRouter: () => ({ push: () => undefined, refresh: () => undefined }),
}));
vi.mock("next/link", async () => {
  const { createElement } = await import("react");
  return {
    default: (p: { href: string; className?: string; children?: unknown }) =>
      createElement("a", { href: p.href, className: p.className }, p.children as never),
  };
});

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const { Dock, DOCK_PHONE } = await import("@/components/shell/phone");
const { ShellFrame } = await import("@/components/shell/frame");

/** jsdom has no matchMedia: the queries given hold, and each listener hears a change of its own query. */
let held: string[] = [];
const heard = new Map<string, Set<() => void>>();
function mediaHolds(...queries: string[]) {
  held = queries;
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (media: string) => ({
      get matches() {
        return held.includes(media);
      },
      media,
      addEventListener: (_: string, cb: () => void) => {
        if (!heard.has(media)) heard.set(media, new Set());
        heard.get(media)!.add(cb);
      },
      removeEventListener: (_: string, cb: () => void) => heard.get(media)?.delete(cb),
    }),
  });
}
function mediaChange(...queries: string[]) {
  const before = held;
  held = queries;
  act(() => {
    for (const [media, cbs] of heard)
      if (before.includes(media) !== held.includes(media)) for (const cb of [...cbs]) cb();
  });
}

/** A ResizeObserver that runs when the test says the dock changed size. */
const watchers: Array<() => void> = [];
class Watcher {
  private cb: () => void;
  constructor(cb: () => void) {
    this.cb = cb;
  }
  observe() {
    watchers.push(this.cb);
  }
  disconnect() {
    const i = watchers.indexOf(this.cb);
    if (i >= 0) watchers.splice(i, 1);
  }
}
/** Each dock's height by its group name (jsdom has no layout). */
const tall = new Map<string, number>();

let shell: HTMLElement;
let page: HTMLElement;
let root: Root;

/** The shell as ShellFrame draws it: the page, then the dock's slot, last in main. */
function withShell(slot = true) {
  shell = document.createElement("main");
  shell.id = "main";
  page = document.createElement("section");
  shell.append(page);
  if (slot) {
    const s = document.createElement("div");
    s.className = "dock-root mo-skip";
    shell.append(s);
  }
  document.body.append(shell);
  root = createRoot(page);
}
const show = (node: ReactNode) => act(() => root.render(node));
const dock = (label: string, className?: string) =>
  h(Dock, { label, className, children: h("button", { type: "button" }, `${label} button`) });
const html = document.documentElement;
const slot = () => document.querySelector("main#main > .dock-root");

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", Watcher);
  vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
    const height = tall.get(this.getAttribute("aria-label") ?? "") ?? 0;
    return { x: 0, y: 0, top: 0, left: 0, right: 360, bottom: height, width: 360, height } as DOMRect;
  });
});

afterEach(() => {
  act(() => root.unmount());
  shell.remove();
  delete (window as { matchMedia?: unknown }).matchMedia;
  held = [];
  heard.clear();
  watchers.length = 0;
  tall.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("C-PHONE-TABS.dock, BLD-D028: a phone's dock lives in the shell's slot and keeps the page's room", () => {
  it("C-PHONE-TABS.dock: on a desk the dock stays where the page put it, with its group name, and keeps no room", () => {
    mediaHolds();
    withShell();
    show(dock("Send your answers"));
    const group = page.querySelector<HTMLElement>('.dock[role="group"]');
    expect(group?.getAttribute("aria-label")).toBe("Send your answers");
    expect(slot()!.children).toHaveLength(0);
    expect(html.hasAttribute("data-dock")).toBe(false);
    expect(html.style.getPropertyValue("--dock-h")).toBe("");
  });

  it("C-PHONE-TABS.dock: on a phone it renders in the slot at the end of main, out of the page's own element, with the page's class kept", () => {
    mediaHolds(DOCK_PHONE);
    withShell();
    show(dock("Move between questions", "ed-dock"));
    expect(page.querySelector(".dock")).toBeNull();
    const moved = slot()!.querySelector<HTMLElement>(".dock");
    expect(moved?.className).toBe("dock ed-dock");
    expect(moved?.getAttribute("role")).toBe("group");
    expect(moved?.getAttribute("aria-label")).toBe("Move between questions");
    // Still in the main landmark, last in its reading order
    expect(shell.lastElementChild?.contains(moved!)).toBe(true);
  });

  it("C-PHONE-TABS.dock: it measures itself as --dock-h with data-dock, follows its own resize, and both go when it unmounts", () => {
    mediaHolds(DOCK_PHONE);
    withShell();
    tall.set("Send your answers", 162.4);
    show(dock("Send your answers"));
    expect(html.style.getPropertyValue("--dock-h")).toBe("163px");
    expect(html.hasAttribute("data-dock")).toBe(true);
    tall.set("Send your answers", 190);
    act(() => watchers.forEach((w) => w()));
    expect(html.style.getPropertyValue("--dock-h")).toBe("190px");
    show(null);
    expect(html.style.getPropertyValue("--dock-h")).toBe("");
    expect(html.hasAttribute("data-dock")).toBe(false);
    expect(watchers).toHaveLength(0);
  });

  it("C-PHONE-TABS.dock: with two docks the page keeps room for the taller; when it goes, the other's height stays", () => {
    mediaHolds(DOCK_PHONE);
    withShell();
    tall.set("A", 100);
    tall.set("B", 160);
    show(h("div", null, dock("A"), dock("B")));
    expect(html.style.getPropertyValue("--dock-h")).toBe("160px");
    show(h("div", null, dock("A")));
    expect(html.style.getPropertyValue("--dock-h")).toBe("100px");
    expect(html.hasAttribute("data-dock")).toBe(true);
  });

  it("C-PHONE-TABS.dock: turned to a desk, it goes back where the page put it and the room goes; turned back, it moves again", () => {
    mediaHolds(DOCK_PHONE);
    withShell();
    tall.set("Send your answers", 150);
    show(dock("Send your answers"));
    expect(slot()!.querySelector(".dock")).not.toBeNull();
    mediaChange();
    expect(page.querySelector(".dock")).not.toBeNull();
    expect(slot()!.children).toHaveLength(0);
    expect(html.hasAttribute("data-dock")).toBe(false);
    mediaChange(DOCK_PHONE);
    expect(slot()!.querySelector(".dock")).not.toBeNull();
    expect(html.style.getPropertyValue("--dock-h")).toBe("150px");
  });

  it("C-PHONE-TABS.dock: without the shell's slot (a test, a public page) a phone's dock stays in place and still keeps the room", () => {
    mediaHolds(DOCK_PHONE);
    withShell(false);
    tall.set("Send your answers", 120);
    show(dock("Send your answers"));
    expect(page.querySelector(".dock")).not.toBeNull();
    expect(html.style.getPropertyValue("--dock-h")).toBe("120px");
  });

  it("C-PHONE-TABS.dock: ShellFrame puts the slot last in main, with no box of its own and out of the arrival", () => {
    withShell();
    const markup = renderToStaticMarkup(
      h(ShellFrame, {
        signedIn: false,
        personId: null,
        nav: [],
        data: null,
        folded: null,
        children: h("p", null, "The page"),
      }),
    );
    expect(markup).toMatch(/<p>The page<\/p><div class="dock-root mo-skip"><\/div><\/main>$/);
  });
});

describe("C-PHONE-TABS.dock, F-SPACE.cta, BLD-D028: the shell's room and scroll margins come from the dock's height", () => {
  const shellCss = cssRules("app/shell.css");
  const phone = "@media (max-width: 640px)";
  const decl = (selector: string, prop: string, at = phone) =>
    shellCss.find((r) => r.at === at && r.selectors.includes(selector) && r.decls.has(prop))?.decls.get(prop);

  it("C-PHONE-TABS.dock: main keeps the tab bar's room, or the dock's height and 24px when that is taller", () => {
    expect(decl('.shell[data-mode="task"] main#main', "padding-bottom")).toBe(
      "max(calc(120px + env(safe-area-inset-bottom)), calc(var(--dock-h, 0px) + 24px))",
    );
    expect(decl(".shell:not(.shell-public) main#main", "padding-bottom")).toBe(
      "max(calc(96px + env(safe-area-inset-bottom)), calc(var(--dock-h, 0px) + 24px))",
    );
  });

  it("C-PHONE-TABS.dock, WCAG 2.4.11: with a dock on screen a focused or scrolled-to target lands 12px clear of it", () => {
    expect(decl("html[data-dock]", "scroll-padding-bottom")).toBe("var(--dock-h)");
    expect(decl("html[data-dock] *", "scroll-margin-block")).toBe("72px 12px");
    // Without a dock, as before: room for the tab bar
    expect(decl("*", "scroll-margin-block")).toBe("72px 120px");
  });

  it("C-PHONE-TABS.dock: the slot has no box of its own, so nothing set on it can move the dock", () => {
    expect(decl(".dock-root", "display", "")).toBe("contents");
  });

  it("BLD-D035, C-PHONE-TABS.dock: on a phone the dock is one column from the foot up that never wraps, so a capped dock scrolls rather than starting a second column", () => {
    expect(decl(".dock", "flex-direction")).toBe("column-reverse");
    expect(decl(".dock", "flex-wrap")).toBe("nowrap");
    // A reversed column's start is the foot: what passes a page's cap leaves by the top, where the dock scrolls to it
    expect(decl(".dock", "justify-content")).toBe("flex-start");
    // The desk keeps its row at the end of the flow, wrapping (F-SPACE.cta/1)
    expect(decl(".dock", "flex-wrap", "")).toBe("wrap");
    expect(decl(".dock", "justify-content", "")).toBe("flex-end");
    // Every phone rule on .dock in the shell is this one, so nothing later puts the wrap back
    expect(shellCss.filter((r) => r.selectors.includes(".dock") && r.at === phone)).toHaveLength(1);
  });

  it("S-04 Voice first's dock is styled under .dock, not .cz, so it keeps its look in the shell's slot (lane C's file)", () => {
    const compose = cssRules("app/share/compose.css");
    const selectors = compose.flatMap((r) => r.selectors);
    for (const s of [".dock .vdock", ".dock .vdock .tinst", ".dock .vdock .stopb", ".dock .stopsq"])
      expect(selectors, s).toContain(s);
    expect(selectors.filter((s) => /\.cz \.(vdock|stopsq)\b/.test(s))).toEqual([]);
  });
});
