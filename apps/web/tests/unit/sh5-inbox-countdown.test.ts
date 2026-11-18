// @vitest-environment jsdom
/**
 * S-H5 with F-COPY.plurals/3 (BLD-A225, J-TRACK/2): the Inbox's countdown is the worker's words and the worker's pill.
 * "2 days left" is plain, "07:38 left" is warn, "Overdue by 5 hours" is bad, and a date ("By Thu, 19 Nov") stays
 * plain. Before, the pill was guessed from the words ("hour" meant soon), which would have made "Overdue by 5 hours"
 * amber. Synthetic people, server render only.
 */
import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { InboxReader } from "@/app/inbox/inbox-reader";
import type { InboxEntry, InboxList } from "@/server/inbox";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: () => undefined }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("next/link", async () => {
  const { createElement: h } = await import("react");
  return {
    default: (p: { href: string; className?: string; children?: unknown }) =>
      h("a", { href: p.href, className: p.className }, p.children as never),
  };
});

const DUE = "2026-11-20T14:40:00+05:30";

function entry(id: string, due: InboxEntry["due"]): InboxEntry {
  return {
    id,
    kind: "questions",
    from: { id: "u-meera", name: "Meera Iyer", first_name: "Meera", initials: "MI" },
    idea: { id: `IDEA-2026-00090${id}`, title: `Synthetic idea ${id}`, status: "needs_you" },
    line: "asked you 3 questions",
    at: new Date().toISOString(),
    unread: false,
    needs_you: true,
    due,
    archived: false,
    body: { heading: "Questions from the review desk", note: "", sender: "Meera from the review desk" },
    actions: [],
  } as InboxEntry;
}

function dues(items: InboxEntry[]): [string | null, string][] {
  const initial: InboxList = {
    items,
    total: items.length,
    counts: { all: 4, needs_you: 4, unread: 0, archived: 0 },
    unread: 0,
  };
  const host = document.createElement("div");
  host.innerHTML = renderToString(
    createElement(InboxReader, { initial, initialTab: "all", initialItem: null }),
  );
  const seen = new Map<string, string>();
  for (const el of Array.from(host.querySelectorAll(".ibx-due"))) {
    const tone = ["over", "soon"].find((t) => el.classList.contains(t)) ?? "";
    seen.set(el.textContent ?? "", tone);
  }
  return [...seen.entries()].map(([label, tone]) => [label, tone]);
}

describe("S-H5 F-COPY.plurals/3: the Inbox countdown's pill comes from the worker (BLD-A225)", () => {
  it("J-TRACK/2: 2 days left is plain, 07:38 left is warn, Overdue by 5 hours is bad, a date stays plain", () => {
    const got = dues([
      entry("1", { at: DUE, label: "2 days left", variant: "normal" }),
      entry("2", { at: DUE, label: "07:38 left", variant: "warn" }),
      entry("3", { at: DUE, label: "Overdue by 5 hours", variant: "bad" }),
      entry("4", { at: DUE, label: "By Fri, 20 Nov" }),
    ]);
    expect(got).toEqual(
      expect.arrayContaining([
        ["2 days left", ""],
        ["07:38 left", "soon"],
        ["Overdue by 5 hours", "over"],
        ["By Fri, 20 Nov", ""],
      ]),
    );
    expect(got).toHaveLength(4);
  });
});
