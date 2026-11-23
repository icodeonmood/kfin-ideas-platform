/** BLD-C236, C-FILE.row: a file whose check waits for the gatekeeper (the assistant is off) is asked about every 30 s,
 * not every 2 s, while every moving file waits; one file still moving brings back the 2 s ask. */
import { describe, expect, it } from "vitest";

const model = await import("@/app/share/[id]/check/model");

const WAITING = "Waiting for the personal details check. It runs when the assistant is back.";

function row(state: string, problem?: string): Parameters<typeof model.waitingForCheck>[0] {
  return {
    key: state,
    name: "form.pdf",
    item: { id: "f1", kind: "file", name: "form.pdf", state, problem },
  } as never;
}

describe("BLD-C236 C-FILE.row: asking less often while a file waits for the gatekeeper", () => {
  it("knows a waiting file by the worker's line on its checking row", () => {
    expect(model.waitingForCheck(row("checking", WAITING))).toBe(true);
    expect(model.waitingForCheck(row("checking"))).toBe(false);
    expect(model.waitingForCheck(row("uploading"))).toBe(false);
  });

  it("asks every 30 s while every moving file waits, and every 2 s otherwise", () => {
    expect(model.pollDelay(0)).toBe(2000);
    expect(model.pollDelay(0, true)).toBe(30_000);
    expect(model.pollDelay(3, true)).toBe(30_000); // a failed ask never makes it ask sooner
    expect(model.pollDelay(9)).toBe(30_000); // the failed-ask cap is unchanged
  });
});
