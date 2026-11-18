// @vitest-environment jsdom
/**
 * The shell's Inbox number in C-SIDEBAR and C-PHONE-TABS (L-INBOX.rules/1, V-ACC.track/8; agreed with lane D): it
 * starts from the server's `inboxCounts(me).unread` (`ShellData.inboxUnread`), follows every count the Inbox sends on
 * `inbox:counts`, and goes back to the server's number when the page's data changes. Synthetic person only.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PhoneTabs } from "@/components/shell/phone";
import { Sidebar } from "@/components/shell/sidebar";
import { COUNTS_EVENT } from "@/lib/inbox-events";
import type { NavItem } from "@/lib/rbac";
import type { ShellData } from "@/server/shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: () => undefined, refresh: () => undefined }),
}));
vi.mock("next/link", async () => {
  const { createElement: h } = await import("react");
  return {
    default: (p: { href: string; className?: string; children?: unknown }) =>
      h("a", { href: p.href, className: p.className }, p.children as never),
  };
});

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const NAV: NavItem[] = [
  { key: "home", label: "Home", href: "/", place: "main", tab: 1 },
  { key: "share", label: "Share a problem", href: "/share", place: "new", tab: 3 },
  { key: "inbox", label: "Inbox", href: "/inbox", place: "main", tab: 5 },
];

function data(inboxUnread: number): ShellData {
  return {
    name: "Ravi Nair",
    initials: "RN",
    tier: null,
    tierName: null,
    inboxUnread,
    drafts: [],
    ideas: [],
  };
}

let host: HTMLElement;
let root: Root;

beforeEach(() => {
  window.matchMedia = ((q: string) => ({
    matches: false,
    media: q,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  })) as unknown as typeof window.matchMedia;
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

function render(unread: number) {
  act(() =>
    root.render(createElement(Sidebar, { personId: "p-ravi", nav: NAV, data: data(unread), folded: null })),
  );
}

function renderTabs(unread: number) {
  act(() => root.render(createElement(PhoneTabs, { nav: NAV, unread })));
}

function inboxLink(): string {
  const link = Array.from(host.querySelectorAll("a")).find((a) => a.getAttribute("href") === "/inbox");
  return link?.textContent ?? "";
}

function send(detail: unknown) {
  act(() => {
    window.dispatchEvent(new CustomEvent(COUNTS_EVENT, { detail }));
  });
}

describe("C-SIDEBAR: the Inbox number", () => {
  it("L-INBOX.rules/1: starts from the server's unread count and follows every count the Inbox sends", () => {
    render(2);
    expect(inboxLink()).toBe("Inbox2, 2 unread");
    send({ all: 4, needs_you: 1, unread: 1, archived: 0 });
    expect(inboxLink()).toBe("Inbox1, 1 unread");
    send({ all: 4, needs_you: 0, unread: 0, archived: 0 });
    expect(inboxLink()).toBe("Inbox"); // none unread: no number
    send(null); // not a count: ignored
    expect(inboxLink()).toBe("Inbox");
  });

  it("V-ACC.track/8: a new number from the server replaces the last one the Inbox sent", () => {
    render(2);
    send({ unread: 0 });
    expect(inboxLink()).toBe("Inbox");
    render(3); // the page's data was read again (router.refresh, or another page)
    expect(inboxLink()).toBe("Inbox3, 3 unread");
  });
});

describe("C-PHONE-TABS: the Inbox tab's number", () => {
  it("L-INBOX.rules/1: starts from the server's unread count and follows every count the Inbox sends", () => {
    renderTabs(2);
    expect(inboxLink()).toBe("2Inbox, 2 new");
    send({ all: 4, needs_you: 1, unread: 1, archived: 0 });
    expect(inboxLink()).toBe("1Inbox, 1 new");
    send({ all: 4, needs_you: 0, unread: 0, archived: 0 });
    expect(inboxLink()).toBe("Inbox"); // none unread: no number
  });

  it("V-ACC.track/8: a new number from the server replaces the last one the Inbox sent", () => {
    renderTabs(2);
    send({ unread: 0 });
    expect(inboxLink()).toBe("Inbox");
    renderTabs(3);
    expect(inboxLink()).toBe("3Inbox, 3 new");
  });

  it("ignores anything that is not a count", () => {
    renderTabs(2);
    for (const detail of [
      null,
      {},
      { unread: "1" },
      { unread: -1 },
      { unread: 1.5 },
      { unread: Number.NaN },
    ]) {
      send(detail);
    }
    expect(inboxLink()).toBe("2Inbox, 2 new");
  });
});
