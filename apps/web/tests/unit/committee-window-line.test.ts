// @vitest-environment jsdom
/**
 * S-R4.layout/3, S-R4.rules/2: the "Your window" cell's line as the Committee board draws it (`.cwl`, `.cext`).
 * "Extended" is a 12px label without a dot, on one line with the days left; the days left turn amber text with the
 * bar when 7 office days or fewer are left. Synthetic people only.
 */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { CommitteeView } from "@/app/committee/committee-view";
import type { CommitteeResponse, CommitteeRow } from "@/lib/contracts";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: () => undefined, push: () => undefined }),
}));
vi.mock("next/link", async () => {
  const { createElement: h } = await import("react");
  return {
    default: (p: { href: string; className?: string; children?: unknown }) =>
      h("a", { href: p.href, className: p.className }, p.children as never),
  };
});

const DAY = 86_400_000;
const at = (ms: number) => new Date(Date.now() + ms).toISOString();
const KAVYA = {
  id: "u-kavya",
  name: "Kavya Menon",
  first_name: "Kavya",
  initials: "KM",
  city: null,
  area: null,
};

function row(daysLeft: number, extended: boolean): CommitteeRow {
  return {
    window_id: `w-${daysLeft}-${extended ? "x" : "o"}`,
    kind: "decision",
    idea: {
      id: "IDEA-2026-001481",
      title: "Investors call to ask why a redemption was held",
      meta: "IDEA-2026-001481, Kavya Menon, Investor service, Hyderabad",
    },
    sharer: KAVYA,
    decision: {
      choice: "pick",
      label: "Picked",
      merged_into: null,
      by_line: "by Meera from the review desk, Monday 16 November",
      reason: "Picked. A clear problem, a real number and a simple fix.",
      reason_heading: "The review desk’s reason, as Kavya read it",
    },
    window: {
      state: extended ? "extended" : "open",
      opens_at: at(-(extended ? 40 : 10) * DAY),
      closes_at: at(daysLeft * DAY),
      max_closes_at: at((extended ? 52 : 82) * DAY),
      extended_times: extended ? 1 : 0,
      left: `${daysLeft} days left`,
      until: "Until Wednesday 16 December",
      extended: extended ? "Extended once" : null,
      extend_to: "Extend to Friday 15 January 2027",
      limit_line: null,
      closed_line: null,
      open_line: "Open until Wednesday 16 December.",
    },
    reversal: null,
    can_extend: true,
    can_reverse: true,
    action: "Review",
    area: "Investor service",
  };
}

function cell(r: CommitteeRow): HTMLElement {
  const initial: CommitteeResponse = {
    items: [r],
    total: 1,
    counts: { window: 1, reversed: 0, expired: 0 },
    summary: "1 decision open to review.",
    explanation: "The review desk decides on the committee’s behalf, and the sharer hears at once.",
  };
  const box = document.createElement("div");
  box.innerHTML = renderToStaticMarkup(
    createElement(CommitteeView, {
      initial,
      tab: "window",
      sort: "closing",
      noteMin: 20,
      returnMonths: [1, 3, 6],
    }),
  );
  const td = box.querySelector<HTMLElement>("td.cm-win");
  if (!td) throw new Error("no window cell");
  return td;
}

describe("S-R4 window line (Committee board .cwl, .cext)", () => {
  it("S-R4.layout/3, S-R4.rules/2: an extended row shows Extended as a label without a dot, beside the days left", () => {
    const td = cell(row(17, true));
    const line = td.querySelector(".cm-wl");
    expect(line).not.toBeNull();
    const ext = line!.querySelector(".cm-ext");
    expect(ext?.textContent).toBe("Extended");
    expect(ext?.querySelector("i")).toBeNull(); // no dot
    expect(ext?.children.length).toBe(0);
    expect(td.querySelector(".pill")).toBeNull();
    expect(line!.querySelector("b.cm-left")?.textContent).toBe("17 days left");
    // The words are read as words: "Extended 17 days left", then the meta line keeps "Extended once"
    expect(line!.textContent).toBe("Extended 17 days left");
    expect(td.querySelector(".meta")?.textContent).toBe("Until Wednesday 16 December. Extended once");
  });

  it("S-R4.layout/3: a window with 7 office days or fewer left marks the days left with the soon tone", () => {
    const left = cell(row(5, false)).querySelector("b.cm-left");
    expect(left?.textContent).toBe("5 days left");
    expect(left?.classList.contains("soon")).toBe(true);
  });

  it("S-R4.layout/3, S-R4.rules/2: an extended row with 5 days left shows the Extended label and the days left in the soon tone", () => {
    const td = cell(row(5, true));
    const line = td.querySelector(".cm-wl");
    expect(line?.querySelector(".cm-ext")?.textContent).toBe("Extended");
    const left = line?.querySelector("b.cm-left");
    expect(left?.textContent).toBe("5 days left");
    expect(left?.classList.contains("soon")).toBe(true);
    expect(line?.textContent).toBe("Extended 5 days left");
  });

  it("S-R4.layout/3: a window with 20 days left keeps the days left in ink, and an unextended row has no label", () => {
    const td = cell(row(20, false));
    const left = td.querySelector("b.cm-left");
    expect(left?.textContent).toBe("20 days left");
    expect(left?.classList.contains("soon")).toBe(false);
    expect(td.querySelector(".cm-ext")).toBeNull();
  });
});
