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
    // The org-wide announcement names Ones, so it waits while they are off the wall (Ones review).
    expect(switchesFor("POST", "/api/ones/announce")).toEqual(["ones.public"]);
    expect(switchesFor("POST", "/api/ones/proposals")).toEqual([]);
    // Running a learning loop by hand stops with the scheduled ones; deciding a proposal does not (§5).
    expect(switchesFor("POST", "/api/learning/run")).toEqual(["learning.jobs"]);
    expect(switchesFor("POST", "/api/learning/proposals/3/decide")).toEqual([]);
    expect(switchesFor("PUT", "/api/delivery/4/pack")).toEqual([]);
  });

  it("has plain-words banner text for every switch it uses", () => {
    for (const rule of ROUTE_RULES) for (const s of rule.switches) expect(BANNERS[s]).toBeTruthy();
    for (const text of Object.values(BANNERS))
      expect(text).not.toMatch(/duplicate|rejected|kill switch|503/i);
  });
});

describe("kill switch coverage", () => {
  it("gates HEAD exactly like GET (Next.js runs the GET handler for HEAD)", () => {
    expect(switchesFor("HEAD", "/api/attachments/ATT-2026-000001")).toEqual(["attachments.open"]);
    expect(switchesFor("head", "/api/wall")).toEqual(["wall.public"]);
  });

  it("every write route file is guarded or explicitly listed as unguarded", async () => {
    const { readdirSync, readFileSync, statSync } = await import("node:fs");
    const path = await import("node:path");
    const { UNGUARDED_WRITES } = await import("@/lib/killswitch-routes");
    const apiRoot = path.resolve(__dirname, "../../src/app/api");
    const routeFiles: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const full = path.join(dir, name);
        if (statSync(full).isDirectory()) walk(full);
        else if (name === "route.ts") routeFiles.push(full);
      }
    };
    walk(apiRoot);
    const ungated: string[] = [];
    for (const file of routeFiles) {
      // Turn the file path into a concrete sample URL: [id] segments become "x".
      const url =
        "/api/" +
        path
          .relative(apiRoot, path.dirname(file))
          .split(path.sep)
          .map((seg) => (seg.startsWith("[") ? "x" : seg))
          .join("/");
      const source = readFileSync(file, "utf8");
      for (const method of ["POST", "PUT", "PATCH", "DELETE"]) {
        if (!new RegExp(`export (async )?function ${method}\\b`).test(source)) continue;
        const guarded = switchesFor(method, url).length > 0;
        const listed = UNGUARDED_WRITES.some((re) => re.test(url));
        if (!guarded && !listed) ungated.push(`${method} ${url}`);
      }
    }
    expect(ungated).toEqual([]);
  });
});
