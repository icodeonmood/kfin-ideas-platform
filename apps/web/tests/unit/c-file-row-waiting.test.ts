/**
 * C-FILE.row, BLD-C237 (WCAG 2.2.2, L-HIDE.files, BLD-C225): while the assistant is off a file's check waits for the
 * gatekeeper, for hours. The row then shows the worker's waiting line and no spinner, since nothing moves and moving
 * content beside text people use must stop within 5 seconds. A check that runs keeps its spinner. Synthetic names only.
 */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { FileRow } from "@/components/ui/file";

const WAITING = "Waiting for the personal details check. It runs when the assistant is back.";

function row(waiting?: boolean, statusText = WAITING): string {
  return renderToStaticMarkup(
    createElement(FileRow, {
      name: "branch-call-log-nov.pdf",
      size: "140 KB",
      status: "checking",
      statusText,
      waiting,
    }),
  );
}

describe("C-FILE.row BLD-C237 WCAG 2.2.2: a waiting check has no spinner", () => {
  it("C-FILE.row BLD-C237: with `waiting` the row has no spinner and the same words, still a checking row", () => {
    const html = row(true);
    expect(html).not.toContain('class="spin"');
    expect(html).toContain(WAITING);
    expect(html).toContain("frow-checking");
  });

  it("C-FILE.row BLD-C237: without `waiting` a checking row keeps its spinner as today", () => {
    const html = row(undefined, "Checking for personal details");
    expect(html).toContain('class="spin"');
    expect(html).toContain("Checking for personal details");
  });

  it("C-FILE.row BLD-C237: `waiting` never takes the spinner from a row that isn't checking (uploading has none)", () => {
    const html = renderToStaticMarkup(
      createElement(FileRow, {
        name: "branch-call-log-nov.pdf",
        status: "checked",
        statusText: "Checked",
        waiting: true,
      }),
    );
    expect(html).not.toContain('class="spin"');
    expect(html).toContain("Checked");
  });
});
