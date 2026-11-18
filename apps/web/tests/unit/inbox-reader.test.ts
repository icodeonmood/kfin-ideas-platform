// @vitest-environment jsdom
/**
 * C-INBOX-READER with S-H2B open, against mocked routes (lane F's f/teamup-4 shapes, synthetic people):
 * BLD-F024 (d) a 409 `not_waiting` on answering ends the request in place as withdrawn, hides the answers, takes the
 * item off "Needs you" and the shell hears the new counts (COUNTS_EVENT); the 30 s refresh also tells the shell
 * (L-INBOX.rules/1, V-ACC.track/8); on a phone the open item's title is the screen's h1 (WCAG 2.1 AA), and nothing
 * is marked read until the person opens it, though the server renders the desktop layout with the first item open.
 */
import { act, createElement } from "react";
import { createRoot, hydrateRoot, type Root } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { COUNTS_EVENT, InboxReader } from "@/app/inbox/inbox-reader";
import type { InboxCounts, InboxEntry, InboxList } from "@/server/inbox";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: () => undefined }),
  useSearchParams: () => new URLSearchParams(globalThis.location?.search ?? ""),
}));
vi.mock("next/link", async () => {
  const { createElement: h } = await import("react");
  return {
    default: (p: { href: string; className?: string; children?: unknown }) =>
      h("a", { href: p.href, className: p.className }, p.children as never),
  };
});

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const RID = "5b0e7a3c-2d41-4f6e-9a18-0c7d3e2b9f11";

const REQUEST: InboxEntry = {
  id: "41",
  kind: "teamup_request",
  from: { id: "u-kavya", name: "Kavya Menon", first_name: "Kavya", initials: "KM" },
  idea: {
    id: "IDEA-2026-000900",
    title: "Rejection SMS codes confuse investors",
    status: "with_review_desk",
  },
  line: "asks to team up and merge their idea into yours",
  at: new Date().toISOString(),
  unread: false,
  needs_you: true,
  archived: false,
  body: { heading: "Merge request", note: "", sender: "Kavya Menon", request_id: RID },
  actions: [
    { label: "Decline", style: "text", op: "decline" },
    { label: "Team up only", style: "line", op: "team_only" },
    { label: "Merge it", style: "primary", op: "merge" },
  ],
} as InboxEntry;

const BEFORE: InboxCounts = { all: 1, needs_you: 1, unread: 0, archived: 0 };
const AFTER: InboxCounts = { all: 1, needs_you: 0, unread: 0, archived: 0 };

/** Lane F's lead view of the waiting merge request (`GET /team-up/:id`). */
const WAITING = {
  id: RID,
  request: "merge",
  note: "I take these calls at our branch every day, about 40 a day.",
  brought: [{ id: "d-1", title: "Investors call to ask why a redemption was rejected", status: "draft" }],
  state: "sent",
  reader: { note_heading: "Kavya’s note", brought_heading: "The idea Kavya asks you to merge into yours" },
};

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

let host: HTMLElement;
let root: Root;
let calls: string[];
let heard: InboxCounts[];
let counts: InboxCounts;
const onCounts = (e: Event) => heard.push((e as CustomEvent<InboxCounts>).detail);

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
  heard = [];
  counts = BEFORE;
  stubWidth(true);
  window.addEventListener(COUNTS_EVENT, onCounts);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push(`${method} ${url}`);
      if (url === `/api/team-up/${RID}`) return json(200, WAITING);
      if (url === `/api/team-up/${RID}/answer`) {
        counts = AFTER; // lane F settled it as withdrawn and resolved the item (BLD-F024)
        return json(409, { error: { code: "not_waiting", message: "Kavya withdrew this request." } });
      }
      if (url === "/api/inbox/counts") return json(200, counts);
      if (url.startsWith("/api/inbox?tab=")) {
        const list: InboxList = { items: [REQUEST], total: 1, counts, unread: 0 };
        return json(200, list);
      }
      return json(404, { error: { code: "not_found", message: "We couldn’t find that." } });
    }),
  );
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  window.removeEventListener(COUNTS_EVENT, onCounts);
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

async function settle() {
  for (let i = 0; i < 5; i++) await act(async () => await Promise.resolve());
}

async function open(initialItem: string | null = REQUEST.id) {
  const initial: InboxList = { items: [REQUEST], total: 1, counts: BEFORE, unread: 0 };
  await act(async () => {
    root.render(createElement(InboxReader, { initial, initialTab: "all", initialItem }));
  });
  await settle();
}

function button(name: string): HTMLButtonElement | undefined {
  return Array.from(host.querySelectorAll("button")).find((b) => b.textContent?.trim() === name);
}

describe("C-INBOX-READER with a request open", () => {
  it("BLD-F024 (d): a 409 not_waiting ends the request as withdrawn in place, and the shell hears the new counts", async () => {
    await open();
    expect(host.textContent).toContain("Kavya’s note");
    expect(button("Merge it")).toBeDefined();

    await act(async () => button("Merge it")!.click());
    await settle();

    expect(calls).toContain(`POST /api/team-up/${RID}/answer`);
    expect(host.querySelector("[role=status].ibx-result")?.textContent).toBe("Kavya withdrew this request.");
    for (const name of ["Decline", "Team up only", "Merge it", "Next"]) expect(button(name)).toBeUndefined();
    expect(host.querySelector(".ibx-read .ibx-bar")).toBeNull(); // the answers' bar is gone
    expect(host.textContent).not.toContain("Investors call to ask why a redemption was rejected"); // BLD-F022
    expect(host.querySelector("[role=alert]")).toBeNull(); // not a generic error
    // The item left "Needs you": every count was fetched again and the shell heard it.
    expect(calls).toContain("GET /api/inbox/counts");
    expect(heard.at(-1)).toEqual(AFTER);
    expect(host.querySelector("#ibx-tab-needs_you")?.textContent).toContain("0");
  });

  it("L-INBOX.rules/1: the 30 s refresh sends every count to the shell", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    await open();
    heard = [];
    counts = AFTER;
    await act(async () => {
      vi.advanceTimersByTime(30_000);
    });
    await settle();
    expect(calls).toContain("GET /api/inbox?tab=all");
    expect(heard).toEqual([AFTER]);
  });

  it("S-H5.rules/6 WCAG 2.1 AA: on a phone the open item's title is the screen's h1; on desktop it is an h2", async () => {
    stubWidth(false);
    await open();
    const h1s = Array.from(host.querySelectorAll("h1")).map((h) => h.textContent);
    expect(h1s).toEqual(["Inbox", "Rejection SMS codes confuse investors"]); // the list's h1 is hidden with the list
    expect(host.querySelector(".ibx-reading")).not.toBeNull();
    act(() => root.unmount());
    root = createRoot(host);
    stubWidth(true);
    await open();
    expect(host.querySelector("#ibx-title")?.tagName).toBe("H2");
  });

  it("S-H5.rules/6: on a phone, hydrating the server's desktop render marks nothing read until an item is opened", async () => {
    stubWidth(false);
    const unread: InboxEntry = {
      ...REQUEST,
      id: "42",
      kind: "mention",
      line: "mentioned you",
      unread: true,
      needs_you: false,
      body: { heading: "", note: "", sender: "Kavya Menon" },
      actions: [],
    } as InboxEntry;
    const initial: InboxList = { items: [unread], total: 1, counts: { ...BEFORE, unread: 1 }, unread: 1 };
    const el = createElement(InboxReader, { initial, initialTab: "all", initialItem: null });
    const server = document.createElement("div");
    server.innerHTML = renderToString(el); // the server's layout: a desktop with the first item open
    document.body.append(server);
    let hydrated: Root | undefined;
    await act(async () => {
      hydrated = hydrateRoot(server, el);
    });
    await settle();
    expect(calls.filter((c) => c.endsWith("/read"))).toEqual([]);
    expect(server.querySelector(".ibx-reading")).toBeNull();
    act(() => hydrated!.unmount());
    server.remove();
  });
});
