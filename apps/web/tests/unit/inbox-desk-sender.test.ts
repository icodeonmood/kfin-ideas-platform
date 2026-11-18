// @vitest-environment jsdom
/**
 * DEC-111 part 2 (BLD-A221), C-INBOX-READER on S-H5 and `/inbox/:itemId`: a desk kind's sender is the review desk as
 * a whole, drawn with the mark and never a reviewer's initials or name, in the row, the reader's header and the
 * row's accessible name, on desktop and phone alike. The worker sends desk kinds that way; the reader holds to it
 * even for an item that still carries a person (one rendered before the change). The 1% Club's own kinds name no
 * one; every other kind keeps its person (L-INBOX.kinds "Sender display"). Synthetic people only.
 */
import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { Avatar, drawsMark, InboxReader, rowName, senderOf } from "@/app/inbox/inbox-reader";
import { REVIEW_DESK_START } from "@/lib/review-desk";
import type { InboxEntry, InboxList } from "@/server/inbox";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: () => undefined }),
  useSearchParams: () => new URLSearchParams(""),
}));
vi.mock("next/link", async () => {
  const { createElement: h } = await import("react");
  return {
    default: (p: { href: string; className?: string; children?: unknown }) =>
      h("a", { href: p.href, className: p.className }, p.children as never),
  };
});

const AT = new Date().toISOString();
const MEERA = { id: "u-meera", name: "Meera Iyer", first_name: "Meera", initials: "MI" };

function entry(kind: InboxEntry["kind"], from: InboxEntry["from"], sender: string, line: string): InboxEntry {
  return {
    id: `i-${kind}`,
    kind,
    from,
    idea: {
      id: "IDEA-2026-000912",
      title: "Investors call to ask why a redemption was rejected",
      status: "needs_you",
    },
    line,
    at: AT,
    unread: true,
    needs_you: false,
    archived: false,
    body: { heading: "", note: "", sender },
    actions: [],
  } as InboxEntry;
}

/** Each desk kind as an item rendered before DEC-111 would carry it: the reviewer by first name, with initials. */
const STALE_DESK = [
  entry("questions", MEERA, "Meera from the review desk", "asked you 3 questions"),
  entry("decision", MEERA, "Meera from the review desk", "picked your idea"),
  entry("worth_revised", MEERA, "Meera from the review desk", "revised what your idea is worth"),
  entry("desk_merge", MEERA, "Meera from the review desk", "merged your idea with Ravi’s"),
  entry("detail_hidden_by_desk", MEERA, "Meera from the review desk", "hid a customer’s detail in your idea"),
];
const FROM_THE_WORKER = entry("questions", "system", REVIEW_DESK_START, "asked you 3 questions");
const REMINDER = entry(
  "answer_reminder",
  MEERA,
  "1% Club",
  "1 day left to answer the review desk’s questions",
);
const TEAMUP = entry(
  "teamup_request",
  { id: "u-kavya", name: "Kavya Menon", first_name: "Kavya", initials: "KM" },
  "Kavya Menon",
  "asks to team up",
);

function html(node: ReturnType<typeof createElement>): string {
  const host = document.createElement("div");
  host.innerHTML = renderToString(node);
  return host.innerHTML;
}

describe("DEC-111 C-INBOX-READER: a desk sender is the review desk, with the mark", () => {
  it("L-INBOX.kinds: every desk kind reads The review desk and draws the 1% mark, never the reviewer's initials", () => {
    for (const item of [...STALE_DESK, FROM_THE_WORKER]) {
      expect(senderOf(item), item.kind).toBe("The review desk");
      expect(drawsMark(item), item.kind).toBe(true);
      const av = html(createElement(Avatar, { item, size: "sm" }));
      expect(av, item.kind).toContain("ibx-av-sm sys");
      expect(av, item.kind).toContain(">1%<");
      expect(av, item.kind).not.toContain("MI");
      expect(rowName(item, new Date()), item.kind).toMatch(/^The review desk /);
      expect(rowName(item, new Date()), item.kind).not.toContain("Meera");
    }
  });

  it("J-TRACK/2–6 S-H5.layout: the row, the open item's header and the item page name the desk, not Meera", () => {
    const items = [...STALE_DESK, REMINDER];
    const initial: InboxList = {
      items,
      total: items.length,
      counts: { all: 6, needs_you: 0, unread: 6, archived: 0 },
      unread: 6,
    };
    // The server's desktop layout has the first item open in the reader (S-H5.rules/2); `/inbox/:itemId` opens one
    for (const initialItem of [null, "i-decision", "i-desk_merge"]) {
      const page = html(createElement(InboxReader, { initial, initialTab: "all", initialItem }));
      expect(page, String(initialItem)).not.toMatch(/Meera|>MI</);
      expect(page, String(initialItem)).toContain("The review desk");
      const host = document.createElement("div");
      host.innerHTML = page;
      const avatars = Array.from(host.querySelectorAll(".ibx-av"));
      expect(avatars.length, String(initialItem)).toBeGreaterThanOrEqual(items.length);
      for (const av of avatars) {
        expect(av.classList.contains("sys"), String(initialItem)).toBe(true);
        expect(av.textContent, String(initialItem)).toBe("1%");
      }
    }
  });

  it("L-INBOX.kinds: the answer reminder is the review desk's (BLD-B257) and draws the mark even when a reviewer sent it", () => {
    expect(drawsMark(REMINDER)).toBe(true);
    expect(senderOf(REMINDER)).toBe("The review desk");
    expect(html(createElement(Avatar, { item: REMINDER, size: "md" }))).not.toContain("MI");
  });

  it("L-INBOX.kinds: a person outside the desk keeps their name and initials", () => {
    expect(senderOf(TEAMUP)).toBe("Kavya Menon");
    expect(drawsMark(TEAMUP)).toBe(false);
    expect(html(createElement(Avatar, { item: TEAMUP, size: "sm" }))).toContain(">KM<");
  });
});
