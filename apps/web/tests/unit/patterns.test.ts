import { describe, expect, it } from "vitest";

import { luhnValid, scan, verhoeffValid } from "@/lib/pii/patterns";

// Synthetic values built at run time (never literals that look like real identifiers).
const rnd = (n: number, first = "0123456789") =>
  first[Math.floor(Math.random() * first.length)] +
  Array.from({ length: n - 1 }, () => String(Math.floor(Math.random() * 10))).join("");

function verhoeffCheck(digits: string): string {
  const d = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
  ];
  const p = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
  ];
  const inv = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9];
  let c = 0;
  [...digits].reverse().forEach((ch, i) => (c = d[c]![p[(i + 1) % 8]![Number(ch)]!]!));
  return String(inv[c]);
}

describe("pattern engine (TypeScript side)", () => {
  it("blocks a checksum-valid Aadhaar and allows the masked form", () => {
    for (let i = 0; i < 20; i++) {
      const body = rnd(11, "23456789");
      const aadhaar = body + verhoeffCheck(body);
      expect(verhoeffValid(aadhaar)).toBe(true);
      expect(scan(`Aadhaar ${aadhaar} in remarks`).map((m) => m.patternId)).toContain("aadhaar");
    }
    expect(scan("Aadhaar XXXX XXXX 1234 is masked").filter((m) => m.action === "block")).toEqual([]);
  });

  it("warns, not blocks, on a KFin email", () => {
    const hits = scan("write to someone@kfintech.com", ["kfintech.com"]);
    expect(hits.map((m) => m.action)).toEqual(["warn"]);
    expect(scan("write to someone@example.com", ["kfintech.com"]).map((m) => m.action)).toEqual(["block"]);
  });

  it("knows Luhn", () => {
    expect(luhnValid("4000000000000002")).toBe(true);
    expect(luhnValid("4000000000000001")).toBe(false);
  });
});
