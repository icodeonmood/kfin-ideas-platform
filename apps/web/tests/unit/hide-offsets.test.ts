import { describe, expect, it } from "vitest";

import { codePointsToUtf16, spansToUtf16, utf16ToCodePoints } from "@/server/hide-offsets";

// L-HIDE.rules/2 and /7 (lane C, BLD-C068): the worker counts code points, the browser UTF-16 units. Synthetic text.
const TEXT = "Call 😀 me on 9876543210 today";
const PHONE = "9876543210";

describe("L-HIDE.rules/2 offsets at the web edge", () => {
  it("moves a span after an emoji by one unit for the underline", () => {
    const cpStart = Array.from(TEXT.slice(0, TEXT.indexOf(PHONE))).length; // code points: the emoji counts once
    const cp = { start: cpStart, end: cpStart + PHONE.length, kind: "phone", hid: "h-1" };
    const [out] = spansToUtf16(TEXT, [cp]);
    expect(TEXT.slice(out!.start, out!.end)).toBe(PHONE);
    expect(out!.start).toBe(cp.start + 1);
    expect(out!.hid).toBe("h-1");
  });

  it("round-trips offsets before and after the emoji", () => {
    const at = TEXT.indexOf(PHONE); // UTF-16 units, as the browser selects
    const cp = utf16ToCodePoints(TEXT, at);
    expect(cp).toBe(at - 1);
    expect(codePointsToUtf16(TEXT, cp!)).toBe(at);
    expect(utf16ToCodePoints(TEXT, 3)).toBe(3);
    expect(codePointsToUtf16(TEXT, TEXT.length)).toBe(TEXT.length);
  });

  it("refuses an offset that splits the emoji or lies outside the text", () => {
    const inside = TEXT.indexOf("😀") + 1;
    expect(utf16ToCodePoints(TEXT, inside)).toBeNull();
    expect(utf16ToCodePoints(TEXT, TEXT.length + 1)).toBeNull();
    expect(utf16ToCodePoints(TEXT, -1)).toBeNull();
  });
});
