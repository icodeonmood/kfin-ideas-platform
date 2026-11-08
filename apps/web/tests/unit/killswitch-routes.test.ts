import { describe, expect, it } from "vitest";

import { BANNERS, ROUTE_RULES, switchesFor } from "@/lib/killswitch-routes";

describe("kill switch route map (§7.6)", () => {
  it("guards every write to submissions and ideas with `submissions`", () => {
    expect(switchesFor("POST", "/api/submissions")).toEqual(["submissions"]);
    expect(switchesFor("PUT", "/api/submissions/abc")).toEqual(["submissions"]);
    expect(switchesFor("POST", "/api/submissions/abc/submit")).toEqual(["submissions"]);
    expect(switchesFor("PUT", "/api/ideas/IDEA-2026-000001/canvas")).toEqual(["submissions"]);
    expect(switchesFor("POST", "/api/ideas/IDEA-2026-000001/plus-one")).toEqual(["submissions"]);
    expect(switchesFor("POST", "/api/clusters/CL-0001/join")).toEqual(["submissions"]);
  });

  it("needs both switches to upload a file", () => {
    expect(switchesFor("POST", "/api/submissions/abc/attachments").sort()).toEqual([
      "attachments.upload",
      "submissions",
    ]);
  });

  it("leaves reads open, except file downloads and the wall", () => {
    expect(switchesFor("GET", "/api/submissions/abc/scan-status")).toEqual([]);
    expect(switchesFor("GET", "/api/ideas/IDEA-2026-000001")).toEqual([]);
    expect(switchesFor("GET", "/api/health")).toEqual([]);
    expect(switchesFor("GET", "/api/attachments/ATT-2026-000001")).toEqual(["attachments.open"]);
    expect(switchesFor("GET", "/api/attachments/ATT-2026-000001/status")).toEqual([]);
    expect(switchesFor("GET", "/api/wall")).toEqual(["wall.public"]);
  });

  it("has plain-words banner text for every switch it uses", () => {
    for (const rule of ROUTE_RULES) for (const s of rule.switches) expect(BANNERS[s]).toBeTruthy();
    for (const text of Object.values(BANNERS))
      expect(text).not.toMatch(/duplicate|rejected|kill switch|503/i);
  });
});
