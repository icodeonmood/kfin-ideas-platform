import { describe, expect, it } from "vitest";

import { BANNERS, ROUTE_RULES, switchesFor } from "@/lib/killswitch-routes";

describe("kill switch route map (§7.6)", () => {
  it("guards every write to submissions and ideas with `submissions`", () => {
    expect(switchesFor("POST", "/api/submissions")).toEqual(["submissions"]);
    expect(switchesFor("PUT", "/api/submissions/abc")).toEqual(["submissions"]);
    expect(switchesFor("POST", "/api/submissions/abc/submit")).toEqual(["submissions"]);
    expect(switchesFor("PUT", "/api/ideas/IDEA-2026-000001/canvas")).toEqual(["submissions"]);
    expect(switchesFor("POST", "/api/ideas/IDEA-2026-000001/answer")).toEqual(["submissions"]);
  });

  it("pauses team-up, a draft's merge request and crew changes with sharing; their reads stay open (BLD-F019)", () => {
    const idea = "/api/ideas/IDEA-2026-000001";
    const req = "/api/team-up/0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10";
    const draft = "/api/drafts/5c2e1a70-6a4b-4f0e-9d1c-7e3b2a1f0c99";
    expect(switchesFor("POST", `${idea}/team-up`)).toEqual(["submissions"]);
    expect(switchesFor("POST", `${req}/answer`)).toEqual(["submissions"]);
    expect(switchesFor("DELETE", req)).toEqual(["submissions"]);
    expect(switchesFor("POST", `${draft}/merge-request`)).toEqual(["submissions"]);
    expect(switchesFor("DELETE", `${draft}/merge-request`)).toEqual(["submissions"]);
    expect(switchesFor("POST", `${idea}/crew/leave`)).toEqual(["submissions"]);
    expect(switchesFor("DELETE", `${idea}/crew/0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a11`)).toEqual([
      "submissions",
    ]);
    for (const read of [`${idea}/team-up`, `${idea}/team-up/draft-note`, req, `${draft}/merge-request`])
      expect(switchesFor("GET", read)).toEqual([]);
  });

  it("an idea's conversation (L-CONVO, BLD-F058): writing and removing a message pause with sharing; reading stays open", () => {
    const base = "/api/ideas/IDEA-2026-001481/conversation";
    expect(switchesFor("POST", `${base}/messages`)).toEqual(["submissions"]);
    expect(switchesFor("DELETE", `${base}/messages/0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10`)).toEqual([
      "submissions",
    ]);
    expect(switchesFor("GET", base)).toEqual([]);
    expect(switchesFor("HEAD", base)).toEqual([]);
  });

  it("needs both switches to upload a file", () => {
    expect(switchesFor("POST", "/api/submissions/abc/attachments").sort()).toEqual([
      "attachments.upload",
      "submissions",
    ]);
  });

  it("voice notes (DEC-096): a new recording needs capture.voice and submissions; reading or deleting one does not need capture.voice", () => {
    expect(switchesFor("POST", "/api/submissions/abc/voice").sort()).toEqual([
      "capture.voice",
      "submissions",
    ]);
    expect(switchesFor("GET", "/api/submissions/abc/voice/0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10")).toEqual([]);
    expect(switchesFor("DELETE", "/api/submissions/abc/voice/0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10")).toEqual([
      "submissions",
    ]);
    // BLD-C149, the product lead's decision of 18 Nov: every voice-off line reads exactly this.
    expect(BANNERS["capture.voice"]).toBe("Voice notes are coming soon.");
    expect(BANNERS["speech.hosted"]).toBe("Voice notes are coming soon.");
    expect(BANNERS["speech.hosted"]).not.toMatch(/sarvam|vendor|third/i);
  });

  it("BLD-E002: sign-in by email code needs auth.email_code; single sign-on needs no switch", () => {
    expect(switchesFor("POST", "/auth/code/send")).toEqual(["auth.email_code"]);
    expect(switchesFor("POST", "/auth/code/verify")).toEqual(["auth.email_code"]);
    expect(switchesFor("POST", "/auth/sso/start")).toEqual([]);
    expect(switchesFor("GET", "/auth/callback")).toEqual([]);
    expect(BANNERS["auth.email_code"]).toBe(
      "Signing in with a code by email is coming soon. Use single sign-on.",
    );
  });

  it("leaves reads open, except file downloads and the wall", () => {
    expect(switchesFor("GET", "/api/submissions/abc/scan-status")).toEqual([]);
    expect(switchesFor("GET", "/api/ideas/IDEA-2026-000001")).toEqual([]);
    expect(switchesFor("GET", "/api/health")).toEqual([]);
    expect(switchesFor("GET", "/api/attachments/ATT-2026-000001")).toEqual(["attachments.open"]);
    expect(switchesFor("GET", "/api/attachments/ATT-2026-000001/status")).toEqual([]);
    expect(switchesFor("GET", "/api/wall")).toEqual(["wall.public"]);
    expect(switchesFor("GET", "/api/display/office")).toEqual(["ones.public"]); // S-OFFICE, non-negotiable 9
    expect(switchesFor("GET", "/api/display/office/x")).toEqual([]);
    expect(switchesFor("POST", "/api/ones/proposals/4/messages")).toEqual([]); // /ones/write/:id (BLD-E042)
    expect(switchesFor("PUT", "/api/delivery/4/pack")).toEqual([]);
  });

  it("has plain-words banner text for every switch it uses", () => {
    for (const rule of ROUTE_RULES) for (const s of rule.switches) expect(BANNERS[s]).toBeTruthy();
    for (const text of Object.values(BANNERS))
      expect(text).not.toMatch(/duplicate|rejected|kill switch|503/i);
  });

  it("speaks the screens' own words: no switch, no in-app inbox, never Garage (BLD-157)", () => {
    for (const text of Object.values(BANNERS)) {
      expect(text).not.toMatch(/\bswitch(ed|es)?\b|in-app|garage/i);
      // "Inbox" is the pack's own word for the screen (S-H5, F-COPY.vocabulary); "inbox" as jargon is not.
      expect(text).not.toMatch(/\binbox\b/);
      expect(text.trim().length).toBeGreaterThan(0);
    }
  });

  it("is the one source: no screen copies a notice's wording (BLD-157)", async () => {
    const { readdirSync, readFileSync, statSync } = await import("node:fs");
    const path = await import("node:path");
    const appRoot = path.resolve(__dirname, "../../src/app");
    const copies: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const full = path.join(dir, name);
        if (statSync(full).isDirectory()) walk(full);
        else if (/\.tsx?$/.test(name)) {
          const source = readFileSync(full, "utf8");
          for (const text of Object.values(BANNERS)) if (source.includes(text)) copies.push(full);
          if (/paused by a switch/i.test(source)) copies.push(full);
        }
      }
    };
    walk(appRoot);
    expect(copies).toEqual([]);
  });

  it("no staff or employee screen talks about switches; the Admin page's own controls may (BLD-157)", async () => {
    const { readdirSync, readFileSync, statSync } = await import("node:fs");
    const path = await import("node:path");
    const src = path.resolve(__dirname, "../../src");
    const allowed = [path.join(src, "app", "admin"), path.join(src, "app", "api")];
    const word = /\bswitch(ed|es)?\b/i;
    const found: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const full = path.join(dir, name);
        if (allowed.some((a) => full.startsWith(a))) continue;
        if (statSync(full).isDirectory()) walk(full);
        else if (/\.tsx?$/.test(name)) {
          const code = readFileSync(full, "utf8")
            .replace(/\/\*[\s\S]*?\*\//g, "")
            .replace(/^\s*\/\/.*$/gm, "")
            .replace(/\brole=["']switch["']/g, ""); // an ARIA role (the P shortcut's toggle), not a word on screen
          // Words people read: string literals and JSX text.
          const strings = code.match(/(["'`])(?:(?!\1)[^\\\n]|\\.)*\1/g) ?? [];
          const jsxText = code.match(/>[^<>{}\n]+</g) ?? [];
          for (const text of [...strings, ...jsxText])
            if (word.test(text) && !/^["'`]Switch to ambient mode["'`]$/.test(text))
              found.push(`${path.relative(src, full)}: ${text}`);
        }
      }
    };
    walk(path.join(src, "app"));
    walk(path.join(src, "components"));
    expect(found).toEqual([]);
  });
});

describe("kill switch coverage", () => {
  it("C-LISTEN: Listen's switch closes the desk's script; lane C's audio and chapters carry lane C's own rule (DEC-108, BLD-B245)", () => {
    expect(switchesFor("GET", "/api/desk/ideas/IDEA-2026-001481/listen")).toEqual(["desk.listen"]);
  });

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
