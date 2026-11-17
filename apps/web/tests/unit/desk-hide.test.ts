import { describe, expect, it } from "vitest";

import { utf16ToCodePoints } from "@/server/hide-offsets";
import {
  HIDE_NEXT,
  HIDE_WORDS,
  extendStep,
  hideBody,
  hideErrorWords,
  hideUrl,
  hideableName,
  opensHide,
  partSource,
  selectionOffsets,
} from "@/lib/desk/hide";
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
    expect(at).toEqual({
      start: TEXT.indexOf(FOLIO),
      end: TEXT.indexOf(FOLIO) + FOLIO.length,
      selected: FOLIO,
    });
    expect(TEXT.slice(at!.start, at!.end)).toBe(FOLIO);
    // the worker's code points sit one before: the emoji is two units and one code point
    expect(utf16ToCodePoints(TEXT, at!.start)).toBe(at!.start - 1);
  });

  it("leaves out the spaces a double-click takes at either end", () => {
    const at = pick(TEXT, ` ${FOLIO} `);
    expect(TEXT.slice(at!.start, at!.end)).toBe(FOLIO);
    expect(at!.selected).toBe(FOLIO);
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

  it("posts the source, the offsets in utf16 units and the selected masked words to lane C's route (BLD-B247)", () => {
    const body = hideBody({ kind: "answer", id: "a-1" }, { start: 14, end: 24, selected: FOLIO });
    expect(body).toEqual({
      source: { kind: "answer", id: "a-1" },
      start: 14,
      end: 24,
      units: "utf16",
      selected: FOLIO,
    });
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
    expect(hideErrorWords("stale")).toBe("The page changed. Select again.");
    expect(hideErrorWords("failed")).toBe(TRY_AGAIN);
  });

  it("uses the curly apostrophe and no internal words", () => {
    for (const line of [...Object.values(HIDE_WORDS), TRY_AGAIN, HIDE_NEXT, hideableName("The problem")]) {
      expect(line).not.toMatch(/'/);
      expect(line).not.toMatch(/invalid|rejected|duplicate/i);
    }
  });
});

const key = (
  k: string,
  mods: Partial<{ shift: boolean; alt: boolean; ctrl: boolean; meta: boolean; code: string }> = {},
) => ({
  key: k,
  code: mods.code,
  shiftKey: mods.shift ?? false,
  altKey: mods.alt ?? false,
  ctrlKey: mods.ctrl ?? false,
  metaKey: mods.meta ?? false,
});

describe("L-HIDE.rules/7 S-R2 Hide this from the keyboard (WCAG 2.1.1, 4.1.3; BLD-B247)", () => {
  it("names each text for a screen reader", () => {
    expect(hideableName("The problem")).toBe("The problem, text");
    expect(HIDE_NEXT).toBe("Hide this is next. Press Tab.");
  });

  it("extends the selection with Shift and an arrow, Home or End", () => {
    expect(extendStep(key("ArrowRight", { shift: true }))).toEqual({
      direction: "forward",
      granularity: "character",
    });
    expect(extendStep(key("ArrowLeft", { shift: true, ctrl: true }))).toEqual({
      direction: "backward",
      granularity: "word",
    });
    expect(extendStep(key("ArrowRight", { shift: true, alt: true }))).toEqual({
      direction: "forward",
      granularity: "word",
    });
    expect(extendStep(key("ArrowDown", { shift: true }))).toEqual({
      direction: "forward",
      granularity: "line",
    });
    expect(extendStep(key("ArrowUp", { shift: true }))).toEqual({
      direction: "backward",
      granularity: "line",
    });
    expect(extendStep(key("End", { shift: true }))).toEqual({
      direction: "forward",
      granularity: "lineboundary",
    });
    expect(extendStep(key("Home", { shift: true }))).toEqual({
      direction: "backward",
      granularity: "lineboundary",
    });
  });

  it("leaves other keys to the browser", () => {
    expect(extendStep(key("ArrowRight"))).toBeNull();
    expect(extendStep(key("ArrowRight", { shift: true, meta: true }))).toBeNull();
    expect(extendStep(key("a", { shift: true }))).toBeNull();
  });

  it("moves to Hide this on Enter or Alt+H, including Option+H on a Mac", () => {
    expect(opensHide(key("Enter"))).toBe(true);
    expect(opensHide(key("h", { alt: true, code: "KeyH" }))).toBe(true);
    expect(opensHide(key("˙", { alt: true, code: "KeyH" }))).toBe(true);
    expect(opensHide(key("Enter", { shift: true }))).toBe(false);
    expect(opensHide(key("h"))).toBe(false);
    expect(opensHide(key("h", { alt: true, ctrl: true, code: "KeyH" }))).toBe(false);
  });
});
