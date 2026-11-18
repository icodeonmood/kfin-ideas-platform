// @vitest-environment jsdom
/**
 * C-SIDEBAR.anatomy/4 and F-A11Y.rules/4: a sidebar dot is never colour alone. Each section says what its dot means:
 * "Your ideas" by the idea's own stage, the review desk's "Waiting on sharers" in the desk's words (reference/copy/
 * Desk.md; S-R1.rules/5: blue normal, amber under a day, red overdue), drafts as "Draft". The committee's dots are all
 * blue and say nothing. Synthetic people and ideas only.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Sidebar } from "@/components/shell/sidebar";
import type { NavItem } from "@/lib/rbac";
import type { MyIdea } from "@/server/ideas";
import { committeeRows, deskRows, ideaRow, type ShellData } from "@/server/shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/desk",
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
  { key: "desk", label: "Review desk", href: "/desk", place: "main" },
];

function idea(over: Partial<MyIdea>): MyIdea {
  return {
    id: "d-1",
    idea_id: "IDEA-2026-000101",
    one_line: "Branch queue times are not tracked anywhere",
    area: "Investor service",
    shared_on: "2026-11-16T09:00:00+05:30",
    draft: false,
    stage: "Reviewed",
    next_step: "",
    due: null,
    stage_key: "reviewed",
    ...over,
  };
}

const desk = deskRows({
  waiting_on_sharers: [
    { idea_id: "IDEA-2026-000201", title: "Nominee updates bounce between two teams", dot: "amber" },
    {
      idea_id: "IDEA-2026-000202",
      title: "Investors call to ask why a redemption was rejected",
      dot: "blue",
    },
    { idea_id: "IDEA-2026-000203", title: "Courier tracking for physical redemption forms", dot: "red" },
  ],
});

const committee = committeeRows({
  items: [
    {
      window_id: "w-1",
      idea: { title: "Plain words for transaction rejections" },
      window: { state: "open", left: "2 days left" },
    },
  ],
} as never);

const DATA: ShellData = {
  name: "Meera Iyer",
  initials: "MI",
  tier: null,
  tierName: null,
  inboxUnread: 0,
  drafts: [{ href: "/share/d-9", title: "Cheque scans at month end", meta: "Today", tone: "draft" }],
  ideas: [
    ideaRow(idea({})),
    ideaRow(
      idea({
        idea_id: "IDEA-2026-000102",
        one_line: "Same KYC details typed into three screens",
        stage: "Needs you",
        stage_key: "needs_you",
      }),
    ),
    ideaRow(
      idea({ idea_id: "IDEA-2026-000103", one_line: "No stage words", stage: " ", stage_key: "asked" }),
    ),
  ],
  desk,
  committee,
};

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
  act(() => root.render(createElement(Sidebar, { personId: "p-meera", nav: NAV, data: DATA, folded: null })));
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

/** The hidden words read before a row's title, by the row's link. */
function spoken(href: string): string | null {
  const link = Array.from(host.querySelectorAll("a")).find((a) => a.getAttribute("href") === href);
  if (!link) throw new Error(`no row for ${href}`);
  return link.querySelector(".vh")?.textContent ?? null;
}

describe("C-SIDEBAR.anatomy/4, F-A11Y.rules/4: each dot says what it means", () => {
  it("Your ideas: the dot reads as the idea's own stage", () => {
    expect(spoken("/ideas/IDEA-2026-000101")).toBe("Reviewed: ");
    expect(spoken("/ideas/IDEA-2026-000102")).toBe("Needs you: ");
  });

  it("Your ideas: with no stage words, the warn dot still reads 'Needs you'", () => {
    expect(spoken("/ideas/IDEA-2026-000103")).toBe("Needs you: ");
  });

  it("S-R1.rules/5, Desk.md: the desk's dots read in the desk's words; amber is under a day, not 'Needs you'", () => {
    expect(desk.map((r) => [r.tone, r.words])).toEqual([
      ["warn", "Under a day left"],
      ["blue", "Waiting on the sharer"],
      ["bad", "Overdue"],
    ]);
    expect(spoken("/desk/ideas/IDEA-2026-000201")).toBe("Under a day left: ");
    expect(spoken("/desk/ideas/IDEA-2026-000202")).toBe("Waiting on the sharer: ");
    expect(spoken("/desk/ideas/IDEA-2026-000203")).toBe("Overdue: ");
  });

  it("Drafts keep 'Draft'; the committee's all-blue dots say nothing", () => {
    expect(spoken("/share/d-9")).toBe("Draft: ");
    expect(committee[0]?.words).toBeUndefined();
    expect(spoken("/committee?open=w-1")).toBeNull();
  });
});
