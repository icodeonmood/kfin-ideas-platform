/**
 * S-02.states Session expired mid-draft, L-AUTH.rules/5 (BLD-A179): the draft card says what is kept, built from the
 * draft's sorting and its hidden details (kinds only, never a value).
 */
import { describe, expect, it } from "vitest";

import { keptLine, sortingTouched } from "@/server/auth/drafts";

describe("S-02.states Session expired mid-draft: what is kept", () => {
  it("says the board's line for touched sorting and one hidden folio", () => {
    expect(keptLine({ sorting: true, hidden: ["folio"] })).toBe("Sorting and the folio you hid are kept.");
  });

  it("follows the board's words for the other cases", () => {
    expect(keptLine({ sorting: true, hidden: [] })).toBe("Sorting is kept.");
    expect(keptLine({ sorting: false, hidden: ["pan"] })).toBe("The PAN you hid is kept.");
    expect(keptLine({ sorting: true, hidden: ["folio", "folio"] })).toBe(
      "Sorting and the 2 folios you hid are kept.",
    );
    expect(keptLine({ sorting: false, hidden: ["phone", "phone", "phone"] })).toBe(
      "The 3 phone numbers you hid are kept.",
    );
    expect(keptLine({ sorting: true, hidden: ["folio", "phone"] })).toBe(
      "Sorting and the details you hid are kept.",
    );
    expect(keptLine({ sorting: false, hidden: ["account", "aadhaar"] })).toBe(
      "The details you hid are kept.",
    );
  });

  it("leaves the line out when nothing is kept", () => {
    expect(keptLine({ sorting: false, hidden: [] })).toBeNull();
  });

  it("counts sorting only once the person confirmed or changed it", () => {
    expect(sortingTouched(null, {})).toBe(false);
    expect(sortingTouched(null, { area: { source: "suggested", why: "from your words" } })).toBe(false);
    expect(sortingTouched(null, { area: { source: "changed" } })).toBe(true);
    expect(sortingTouched(null, { kind: { source: "confirmed" }, area: { source: "suggested" } })).toBe(true);
    expect(sortingTouched(new Date("2026-11-20T04:11:00Z"), {})).toBe(true);
    expect(sortingTouched(null, null)).toBe(false);
    expect(sortingTouched(null, ["changed"])).toBe(false);
  });
});
