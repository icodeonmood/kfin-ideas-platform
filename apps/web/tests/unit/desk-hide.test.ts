import { describe, expect, it } from "vitest";

import { utf16ToCodePoints } from "@/server/hide-offsets";
import { HIDE_WORDS, hideBody, hideErrorWords, hideUrl, partSource, selectionOffsets } from "@/lib/desk/hide";
import { TRY_AGAIN } from "@/lib/desk/reply";

// S-R2 "Hide this" (L-HIDE.rules/7, BLD-B246). Synthetic text only (non-negotiable 11).
const TEXT = "Kavya 😀 says folio 7654321/98 keeps bouncing";
const FOLIO = "7654321/98";

function pick(text: string, selected: string) {
  const at = text.indexOf(selected);
  return selectionOffsets(text, text.slice(0, at), selected);
}

describe("L-HIDE.rules/7 S-R2 Hide this: the selection's offsets", () => {
  it("counts UTF-16 units, as the browser does, after an emoji", () => {
    const at = pick(TEXT, FOLIO);
    expect(at).toEqual({ start: TEXT.indexOf(FOLIO), end: TEXT.indexOf(FOLIO) + FOLIO.length });
    expect(TEXT.slice(at!.start, at!.end)).toBe(FOLIO);
    // the worker's code points sit one before: the emoji is two units and one code point
    expect(utf16ToCodePoints(TEXT, at!.start)).toBe(at!.start - 1);
  });

  it("leaves out the spaces a double-click takes at either end", () => {
    const at = pick(TEXT, ` ${FOLIO} `);
    expect(TEXT.slice(at!.start, at!.end)).toBe(FOLIO);
  });

  it("offers nothing for a selection of spaces only, or one that is not this text's", () => {
    expect(selectionOffsets(TEXT, "Kavya", " ")).toBeNull();
    expect(selectionOffsets(TEXT, "Kavya", "")).toBeNull();
    expect(selectionOffsets(TEXT, "Kavya 😀 says", "elsewhere")).toBeNull();
  });

  it("works in Hindi text too", () => {
    const hindi = "शाखा में कॉल 9876501234 पर आई";
    const at = pick(hindi, "9876501234");
    expect(hindi.slice(at!.start, at!.end)).toBe("9876501234");
  });

  it("posts the source and the offsets in utf16 units to lane C's route", () => {
    const body = hideBody({ kind: "answer", id: "a-1" }, { start: 14, end: 24 });
    expect(body).toEqual({ source: { kind: "answer", id: "a-1" }, start: 14, end: 24, units: "utf16" });
    expect(hideUrl("IDEA-2026-001481")).toBe("/api/desk/ideas/IDEA-2026-001481/hide");
  });

  it("maps the parts kept as one text to their source, and no others", () => {
    expect(partSource("summary")).toEqual({ kind: "title", id: "summary" });
    expect(partSource("often")).toEqual({ kind: "title", id: "often" });
    expect(partSource("fix")).toEqual({ kind: "fix", id: "how" });
    expect(partSource("who")).toBeNull();
    expect(partSource("cost")).toBeNull();
    expect(partSource("evidence")).toBeNull();
  });
});

describe("L-HIDE.rules/7 S-R2 Hide this: the words for a refusal", () => {
  it("says each refusal in plain words", () => {
    expect(hideErrorWords("range_invalid")).toBe("Select at least 3 letters or numbers.");
    expect(hideErrorWords("already_hidden")).toBe("That’s already hidden.");
    expect(hideErrorWords("not_found")).toBe("That didn’t go through. Try again.");
    expect(hideErrorWords("failed")).toBe(TRY_AGAIN);
  });

  it("uses the curly apostrophe and no internal words", () => {
    for (const line of [...Object.values(HIDE_WORDS), TRY_AGAIN]) {
      expect(line).not.toMatch(/'/);
      expect(line).not.toMatch(/invalid|rejected|duplicate/i);
    }
  });
});
