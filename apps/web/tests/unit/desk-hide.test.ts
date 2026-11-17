import { describe, expect, it } from "vitest";

import { utf16ToCodePoints } from "@/server/hide-offsets";
import {
  HIDE_NEXT,
  HIDE_WORDS,
  caretStep,
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

  it("moves the caret with an arrow, Home or End, so the selection can start mid-text (R2)", () => {
    expect(caretStep(key("ArrowRight"))).toEqual({
      alter: "move",
      direction: "forward",
      granularity: "character",
    });
    expect(caretStep(key("ArrowLeft"))).toEqual({
      alter: "move",
      direction: "backward",
      granularity: "character",
    });
    expect(caretStep(key("ArrowRight", { ctrl: true }))).toEqual({
      alter: "move",
      direction: "forward",
      granularity: "word",
    });
    expect(caretStep(key("ArrowLeft", { alt: true }), true)).toEqual({
      alter: "move",
      direction: "backward",
      granularity: "word",
    });
    expect(caretStep(key("ArrowDown"))).toEqual({ alter: "move", direction: "forward", granularity: "line" });
    expect(caretStep(key("ArrowUp"))).toEqual({ alter: "move", direction: "backward", granularity: "line" });
    expect(caretStep(key("End"))).toEqual({
      alter: "move",
      direction: "forward",
      granularity: "lineboundary",
    });
    expect(caretStep(key("Home"))).toEqual({
      alter: "move",
      direction: "backward",
      granularity: "lineboundary",
    });
  });

  it("extends the selection from the caret with Shift and an arrow, Home or End", () => {
    expect(caretStep(key("ArrowRight", { shift: true }))).toEqual({
      alter: "extend",
      direction: "forward",
      granularity: "character",
    });
    expect(caretStep(key("ArrowLeft", { shift: true, ctrl: true }))).toEqual({
      alter: "extend",
      direction: "backward",
      granularity: "word",
    });
    expect(caretStep(key("ArrowRight", { shift: true, alt: true }), true)).toEqual({
      alter: "extend",
      direction: "forward",
      granularity: "word",
    });
    expect(caretStep(key("ArrowDown", { shift: true }))).toEqual({
      alter: "extend",
      direction: "forward",
      granularity: "line",
    });
    expect(caretStep(key("ArrowUp", { shift: true }))).toEqual({
      alter: "extend",
      direction: "backward",
      granularity: "line",
    });
    expect(caretStep(key("End", { shift: true }))).toEqual({
      alter: "extend",
      direction: "forward",
      granularity: "lineboundary",
    });
    expect(caretStep(key("Home", { shift: true }))).toEqual({
      alter: "extend",
      direction: "backward",
      granularity: "lineboundary",
    });
  });

  it("leaves the browser's own keys to the browser", () => {
    // Alt and an arrow is Back and Forward off a Mac; Cmd and an arrow is the Mac's own line and page keys
    expect(caretStep(key("ArrowLeft", { alt: true }))).toBeNull();
    expect(caretStep(key("ArrowRight", { shift: true, alt: true }))).toBeNull();
    expect(caretStep(key("ArrowRight", { shift: true, meta: true }))).toBeNull();
    expect(caretStep(key("ArrowLeft", { meta: true }), true)).toBeNull();
    expect(caretStep(key("a", { shift: true }))).toBeNull();
    expect(caretStep(key("Tab"))).toBeNull();
    expect(caretStep(key("Enter"))).toBeNull();
  });

  it("moves to Hide this on Enter only; Alt+H is the browser's Help menu on Windows", () => {
    expect(opensHide(key("Enter"))).toBe(true);
    expect(opensHide(key("Enter", { shift: true }))).toBe(false);
    expect(opensHide(key("Enter", { ctrl: true }))).toBe(false);
    expect(opensHide(key("Enter", { alt: true }))).toBe(false);
    expect(opensHide(key("h", { alt: true, code: "KeyH" }))).toBe(false);
    expect(opensHide(key("˙", { alt: true, code: "KeyH" }))).toBe(false);
    expect(opensHide(key("h"))).toBe(false);
  });

  it("says Select again. when the page's text is not the stored text (R3)", () => {
    expect(HIDE_WORDS.select_again).toBe("Select again.");
  });
});
