// @vitest-environment jsdom
/**
 * DEC-144 (1) and (3), BLD-B284: the review desk shows a green "Checked for personal details" badge on every file it
 * lists once both checks have passed (the worker's `checked`, desk/reads.py `_checked`): the idea's own files and each
 * merged idea's (S-R2.left/2, L-MERGE.effects/3, one row, `FileArtefact`) and the files sent with an answer
 * (S-R2.left/3, C-QCARD). A file the worker does not mark checked (an old-pipeline row whose personal-data check did
 * not run) gets no badge and no other words. A file holding a customer detail carries both labels (DEC-107).
 * Synthetic data only.
 */
import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children?: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: () => undefined, push: () => undefined }),
}));

const { AskedQuestion, FileArtefact } = await import("@/app/desk/ideas/[id]/reviewer-idea");
const { CHECKED_FOR_DETAILS, CUSTOMER_DETAIL } = await import("@/lib/desk/files");
type Artefact = import("@/lib/contracts").ReviewerArtefact;
type Question = import("@/lib/contracts").ReviewerQuestion;
type AnswerFile = NonNullable<Question["answer"]>["files"][number];

const IDEA = "IDEA-2026-000932";

function artefact(extra: Partial<Artefact>): Artefact {
  return {
    kind: "file",
    id: "ATT-2026-500201",
    title: "branch-returns-nov.pdf",
    line: "Attached by Kavya. 140 KB, 3 pages.",
    action: "Open",
    ...extra,
  };
}

function question(files: AnswerFile[]): Question {
  return {
    id: "5d4c3b2a-1f0e-4d9c-8b7a-6f5e4d3c2b1a",
    text: "Can you add the November returns count for branch R07?",
    asked_at: "2026-11-16T05:50:00Z",
    asked_by: "Meera",
    asked_line: "You asked, Monday 16 November, 11:20 am",
    state: "Answered",
    answer: {
      id: "9e8d7c6b-5a4f-4e3d-8c2b-1a0f9e8d7c6b",
      text: "Here it is.",
      at: "2026-11-16T11:02:00Z",
      by: "Kavya",
      line: "Kavya answered, Monday 16 November, 4:32 pm",
      files,
      files_removed: null,
    },
  };
}

function html(el: ReturnType<typeof createElement>): HTMLElement {
  const host = document.createElement("div");
  host.innerHTML = renderToStaticMarkup(el);
  return host;
}

const pills = (root: Element) =>
  [...root.querySelectorAll(".pill")].map((p) => [p.className, p.textContent?.trim()]);

describe("DEC-144 (1), BLD-B284: the desk's Checked for personal details badge", () => {
  it('the words are the lead\'s (DEC-144 (3)), never "PI check verified"', () => {
    expect(CHECKED_FOR_DETAILS).toBe("Checked for personal details");
  });

  it("an idea's file, or a merged idea's, that passed both checks carries the green badge", () => {
    const row = html(createElement(FileArtefact, { a: artefact({ checked: true }) }));
    expect(pills(row)).toEqual([["pill ok", CHECKED_FOR_DETAILS]]);
  });

  it("DEC-107: a file holding a customer detail was checked too, so it carries both labels", () => {
    const row = html(createElement(FileArtefact, { a: artefact({ checked: true, customer_detail: true }) }));
    expect(pills(row)).toEqual([
      ["pill ok", CHECKED_FOR_DETAILS],
      ["pill warn", CUSTOMER_DETAIL],
    ]);
  });

  it("a file the worker does not mark checked gets no badge and no other words", () => {
    for (const a of [artefact({ checked: false }), artefact({})]) {
      const row = html(createElement(FileArtefact, { a }));
      expect(pills(row)).toEqual([]);
      expect(row.textContent).toBe(`PDFbranch-returns-nov.pdfAttached by Kavya. 140 KB, 3 pages.Open`);
    }
  });

  it("the files sent with an answer carry it the same way", () => {
    const host = html(
      createElement(AskedQuestion, {
        ideaId: IDEA,
        q: question([
          {
            id: "ATT-2026-500202",
            name: "returns-R07.xlsx",
            hidden: null,
            customer_detail: false,
            checked: true,
          },
          {
            id: "ATT-2026-500203",
            name: "returns-R08.xlsx",
            hidden: null,
            customer_detail: true,
            checked: true,
          },
          {
            id: "ATT-2026-500204",
            name: "returns-R09.xlsx",
            hidden: null,
            customer_detail: false,
            checked: false,
          },
        ]),
      }),
    );
    const rows = [...host.querySelectorAll(".ri-a-files li")];
    expect(rows.map(pills)).toEqual([
      [["pill ok", CHECKED_FOR_DETAILS]],
      [
        ["pill ok", CHECKED_FOR_DETAILS],
        ["pill warn", CUSTOMER_DETAIL],
      ],
      [],
    ]);
    expect(rows[2]?.textContent).toBe("returns-R09.xlsx");
  });
});
