/**
 * AT-B2-04 (policy half): for every role column in §3.1 and every day-one endpoint in §8, allowed and denied
 * match the matrix. Two checks: (1) a table typed independently from ARCHITECTURE §3.1 must agree with
 * policy/rbac.yaml; (2) a table-driven test over every endpoint × role generated from rbac.yaml.
 * The HTTP half (the proxy really enforces it) is services/worker/tests/test_b2_04_rbac_http.py.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";
import { parse } from "yaml";

import policyJson from "@/lib/rbac.json";
import {
  ENDPOINTS,
  ROLE_COLUMNS,
  can,
  canFlip,
  canSeePage,
  decide,
  effectiveRoles,
  navFor,
  scopesFor,
} from "@/lib/rbac";

const rolesOf = (role: string) => effectiveRoles(role === "contributor" ? [] : [{ role, scope_id: null }]);

// Transcribed by hand from ARCHITECTURE §3.1 (✓ or a scope word = allowed; blank = denied).
const ALL = [
  "contributor",
  "reviewer",
  "lob_committee",
  "core_committee",
  "appeal_panel",
  "working_group",
  "sponsor",
  "admin",
  "committee", // the pack's Ones Committee (E-ENUMS.roles, DEC-102), beside the §3.1 columns until they retire
];
const SECTION_3_1: Record<string, string[]> = {
  submit: ALL,
  see_org_ideas: ALL,
  work_review_queue: ["reviewer", "admin"],
  view_review_queue: ["reviewer", "core_committee", "admin"],
  veto_desk_decision: ["core_committee"],
  open_attachments: ALL,
  see_restored_values: ALL,
  approve_handover: ["sponsor"],
  grant_roles: ["admin"],
  // L-COMMITTEE: the 30-day window, extend, reverse once (lane B); core_committee until Monday (BLD-B238)
  committee_window: ["core_committee", "committee"],
};

describe("policy agrees with ARCHITECTURE §3.1", () => {
  it("lists the eight §3.1 role columns and the pack's committee", () => {
    expect([...ROLE_COLUMNS]).toEqual(ALL);
  });

  for (const [capability, allowed] of Object.entries(SECTION_3_1)) {
    it(capability, () => {
      const actual = ALL.filter((role) => can(rolesOf(role), capability));
      expect(actual).toEqual(allowed);
    });
  }

  it("keeps the scope words the handlers must enforce", () => {
    expect(scopesFor(rolesOf("contributor"), "see_restored_values")).toEqual(["own_idea"]);
  });

  it("treats the chair as a core committee member", () => {
    expect(can(effectiveRoles([{ role: "core_chair", scope_id: null }]), "veto_desk_decision")).toBe(true);
  });
});

describe("every day-one endpoint × every role column (generated from rbac.yaml)", () => {
  const sample = (template: string) => template.replace(/\{[a-z_]+\}/g, "x1");
  for (const endpoint of ENDPOINTS) {
    for (const role of ALL) {
      it(`${endpoint.method} ${endpoint.template} as ${role}`, () => {
        const expected = endpoint.capabilities.some((c) => can(rolesOf(role), c));
        const decision = decide(rolesOf(role), endpoint.method, sample(endpoint.template));
        expect(decision.kind).toBe(expected ? "allow" : "deny");
      });
    }
  }

  it("refuses paths the policy does not list, and treats HEAD as GET", () => {
    expect(decide(rolesOf("admin"), "GET", "/api/not-in-policy").kind).toBe("unknown");
    expect(decide(rolesOf("contributor"), "HEAD", "/api/me").kind).toBe("allow");
    expect(decide(rolesOf("contributor"), "GET", "/api/health").kind).toBe("public");
  });

  it("lets everyone signed in reach an idea's conversation; the worker decides per idea and answers others 404 (L-CONVO/2)", () => {
    const base = "/api/ideas/IDEA-2026-001481/conversation";
    for (const role of ["contributor", "reviewer", "core_committee"]) {
      expect(decide(rolesOf(role), "GET", base).kind).toBe("allow");
      expect(decide(rolesOf(role), "POST", `${base}/messages`).kind).toBe("allow");
      expect(
        decide(rolesOf(role), "DELETE", `${base}/messages/0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10`).kind,
      ).toBe("allow");
    }
    expect(decide(rolesOf("contributor"), "PUT", `${base}/messages`).kind).toBe("unknown");
  });

  it("matches the §8 review rules people care about most", () => {
    expect(decide(rolesOf("reviewer"), "POST", "/api/review/items/7/action").kind).toBe("allow");
    expect(decide(rolesOf("reviewer"), "POST", "/api/review/items/7/veto").kind).toBe("deny");
    expect(decide(rolesOf("core_committee"), "POST", "/api/review/items/7/veto").kind).toBe("allow");
    // A member may act only on an item they vetoed; the proxy lets the request through and the handler checks (BLD-092).
    expect(decide(rolesOf("core_committee"), "POST", "/api/review/items/7/action").kind).toBe("allow");
    expect(decide(rolesOf("contributor"), "POST", "/api/review/items/7/action").kind).toBe("deny");
    expect(decide(rolesOf("contributor"), "GET", "/api/review/items").kind).toBe("deny");
  });
});

describe("navigation and pages (AT-B2-06; C-SIDEBAR, C-PHONE-TABS)", () => {
  const labels = (role: string, place?: string) =>
    navFor(rolesOf(role))
      .filter((n) => !place || n.place === place)
      .map((n) => n.label);
  const base = ["Share a problem", "Home", "Find your crew", "My ideas", "Wall", "Inbox"];
  it("everyone gets Share a problem, Home, Find your crew, My ideas, Wall and Inbox, and Profile and The Ember in the account menu (S-H6)", () =>
    expect(labels("contributor")).toEqual([...base, "Your profile and settings", "The Ember"]));
  it("S-R1: the review desk adds Review desk to the sidebar, at /desk", () => {
    expect(labels("reviewer", "main")).toEqual(["Home", "Find your crew", "Wall", "Inbox", "Review desk"]);
    expect(navFor(rolesOf("reviewer")).find((n) => n.key === "desk")?.href).toBe("/desk");
  });
  it("S-R4: the core committee sees Ones Committee in the sidebar until Monday, and Delivery in the account menu", () => {
    expect(labels("core_committee", "main")).toEqual([
      "Home",
      "Find your crew",
      "Wall",
      "Inbox",
      "Ones Committee",
    ]);
    expect(labels("core_committee", "account")).toEqual([
      "Your profile and settings",
      "The Ember",
      "Delivery",
    ]);
    expect(labels("contributor", "account")).toEqual(["Your profile and settings", "The Ember"]);
  });
  it("S-R4: the pack's committee role (E-ENUMS.roles) sees Ones Committee, as the old core committee does until Monday", () =>
    expect(labels("committee", "main")).toEqual([
      "Home",
      "Find your crew",
      "Wall",
      "Inbox",
      "Ones Committee",
    ]));
  it("admin, InfoSec and HR reach Admin from the account menu, not the sidebar", () => {
    for (const role of ["admin", "infosec", "hr"]) expect(labels(role, "account")).toContain("Admin");
    expect(labels("admin", "main")).toEqual(["Home", "Find your crew", "Wall", "Inbox"]);
  });
  it("C-PHONE-TABS.bar: the tab bar is Home, My ideas, Share, Wall, Inbox for everyone", () => {
    for (const role of ["contributor", "reviewer", "core_committee", "admin"]) {
      const tabs = navFor(rolesOf(role))
        .filter((n) => n.tab)
        .sort((a, b) => (a.tab ?? 0) - (b.tab ?? 0))
        .map((n) => n.key);
      expect(tabs).toEqual(["home", "my-ideas", "share", "wall", "inbox"]);
    }
  });
  it("C-SIDEBAR.anatomy, S-H2: Find your crew is everyone's, straight after Home, at /crew, with no phone tab", () => {
    for (const role of ["contributor", "reviewer", "core_committee", "admin"]) {
      const nav = navFor(rolesOf(role));
      expect(nav.find((n) => n.key === "crew")).toEqual({
        key: "crew",
        label: "Find your crew",
        href: "/crew",
        place: "main",
      });
      expect(
        nav
          .filter((n) => n.place === "main")
          .map((n) => n.key)
          .slice(0, 2),
      ).toEqual(["home", "crew"]);
    }
  });
  it("one Share a problem button; My ideas shows only when the sidebar is folded", () => {
    const nav = navFor(rolesOf("contributor"));
    expect(nav.filter((n) => n.place === "new").map((n) => n.href)).toEqual(["/share"]);
    expect(nav.find((n) => n.key === "my-ideas")?.place).toBe("folded");
  });
  it("S-ONE.rules/1: only an active One gets Your One dashboard, in the account menu; no role grants it (BLD-E040)", () => {
    for (const role of ["contributor", "reviewer", "core_committee", "committee", "admin"]) {
      expect(navFor(rolesOf(role)).map((n) => n.href)).not.toContain("/one");
      expect(navFor(rolesOf(role), new Set(), new Set(["ones"])).find((n) => n.href === "/one")).toEqual({
        key: "one",
        label: "Your One dashboard",
        href: "/one",
        place: "account",
      });
    }
  });
  it("S-H6: Profile is in everyone's account menu", () => {
    for (const role of ["contributor", "reviewer", "core_committee", "admin"])
      expect(navFor(rolesOf(role)).find((n) => n.href === "/profile")?.place).toBe("account");
  });
  it("retired features have no navigation (DEC-106)", () => {
    const hrefs = (policyJson.navigation as Array<{ href: string }>).map((n) => n.href);
    for (const gone of ["/lenses", "/desk-decisions", "/ones/console", "/appeals"])
      expect(hrefs).not.toContain(gone);
  });
  it("pages follow the same rules", () => {
    // /review redirects to /desk (S-R1); its rule keeps everyone else out of the old path
    expect(canSeePage(rolesOf("contributor"), "/review")).toBe(false);
    expect(canSeePage(rolesOf("reviewer"), "/review")).toBe(true);
    // S-R1, S-R2: the review desk and the reviewer's page
    expect(canSeePage(rolesOf("reviewer"), "/desk")).toBe(true);
    expect(canSeePage(rolesOf("reviewer"), "/desk/ideas/IDEA-2026-001481")).toBe(true);
    expect(canSeePage(rolesOf("contributor"), "/desk")).toBe(false);
    expect(canSeePage(rolesOf("contributor"), "/admin")).toBe(false);
    expect(canSeePage(rolesOf("infosec"), "/admin")).toBe(true);
    // S-R4: the Ones Committee's window (committee_window) is the committee role's, and the core committee's (with
    // its chair) until the old roles are dropped on Monday (contracts.md §2.14); LOB committees no longer open it
    expect(canSeePage(rolesOf("committee"), "/committee")).toBe(true);
    expect(canSeePage(rolesOf("core_committee"), "/committee")).toBe(true);
    expect(canSeePage(rolesOf("core_chair"), "/committee")).toBe(true);
    expect(canSeePage(rolesOf("lob_committee"), "/committee")).toBe(false);
    expect(canSeePage(rolesOf("contributor"), "/share")).toBe(true);
  });
  it("S-ONE (mapping/screens.md:111-112): the printable Showcase brief is for the committee, CEO and admin only; the glow-up message page opens for anyone signed in and checks the invitation itself", () => {
    expect(canSeePage(rolesOf("contributor"), "/ones/showcase/3")).toBe(false);
    expect(canSeePage(rolesOf("reviewer"), "/ones/showcase/3")).toBe(false);
    for (const role of ["core_committee", "admin", "ceo"])
      expect(canSeePage(rolesOf(role), "/ones/showcase/3")).toBe(true);
    expect(canSeePage(rolesOf("contributor"), "/ones/write/12")).toBe(true);
  });

  it("never lists a page below a page that already covers it (the first matching rule wins)", () => {
    const paths = (policyJson.pages as string[]).map((line) => line.trim().split(/\s+/)[0]!);
    const shadowed = paths.flatMap((p, i) =>
      paths
        .slice(0, i)
        .filter((q) => p.startsWith(`${q}/`))
        .map((q) => `${p} is below ${q}`),
    );
    expect(shadowed).toEqual([]);
  });

  it("the Ones console: who may propose, approve and carry out (DEC-040)", () => {
    expect(decide(rolesOf("ceo"), "POST", "/api/ones/proposals").kind).toBe("allow");
    expect(decide(rolesOf("admin"), "POST", "/api/ones/proposals").kind).toBe("deny");
    expect(decide(rolesOf("core_committee"), "POST", "/api/ones/proposals/4/decide").kind).toBe("allow");
    expect(decide(rolesOf("ceo"), "POST", "/api/ones/proposals/4/decide").kind).toBe("deny");
    expect(decide(rolesOf("admin"), "POST", "/api/ones/proposals/4/carry-out").kind).toBe("allow");
    expect(decide(rolesOf("core_committee"), "POST", "/api/ones/proposals/4/carry-out").kind).toBe("deny");
    expect(decide(rolesOf("contributor"), "GET", "/api/ones/console").kind).toBe("deny");
    expect(decide(rolesOf("contributor"), "GET", "/api/ones").kind).toBe("allow");
    expect(decide(rolesOf("contributor"), "POST", "/api/me/one/number").kind).toBe("allow");
  });

  it("delivery (BLD-115 to BLD-122)", () => {
    // Anyone may be named owner, PM or milestone owner: the worker serves only their own deliveries.
    expect(decide(rolesOf("contributor"), "GET", "/api/delivery").kind).toBe("allow");
    expect(decide(rolesOf("contributor"), "PUT", "/api/delivery/4/measurements/day_30").kind).toBe("allow");
    expect(decide(rolesOf("contributor"), "POST", "/api/delivery").kind).toBe("deny");
    expect(decide(rolesOf("core_committee"), "POST", "/api/delivery").kind).toBe("allow");
    expect(decide(rolesOf("contributor"), "POST", "/api/delivery/4/approve").kind).toBe("deny");
    expect(decide(rolesOf("sponsor"), "POST", "/api/delivery/4/approve").kind).toBe("allow");
    expect(decide(rolesOf("ceo"), "POST", "/api/delivery/4/measurements/day_90/confirm").kind).toBe("allow");
    expect(decide(rolesOf("sponsor"), "POST", "/api/delivery/4/measurements/day_90/finance").kind).toBe(
      "deny",
    );
    expect(decide(rolesOf("admin"), "POST", "/api/delivery/4/measurements/day_90/finance").kind).toBe(
      "allow",
    );
    expect(canSeePage(rolesOf("contributor"), "/delivery/4")).toBe(true); // their own, or not found
  });
});

describe("kill switch flippers (§7.6)", () => {
  const r = (role: string) => effectiveRoles([{ role, scope_id: null }]);
  it("follows the 'Who can flip' column", () => {
    expect(canFlip(r("admin"), "submissions")).toBe(true);
    expect(canFlip(r("infosec"), "submissions")).toBe(false);
    expect(canFlip(r("infosec"), "attachments.open")).toBe(true);
    expect(canFlip(r("admin"), "attachments.open")).toBe(false);
    expect(canFlip(r("hr"), "wall.public")).toBe(true);
    expect(canFlip(r("admin"), "agent.gatekeeper")).toBe(true);
    expect(canFlip(r("reviewer"), "ai.all")).toBe(false);
    expect(canFlip(r("admin"), "learning.jobs")).toBe(true);
    expect(canFlip(r("infosec"), "learning.jobs")).toBe(false);
  });

  it("voice notes (DEC-096): admin or InfoSec for the tip and voice notes; InfoSec alone for hosted speech", () => {
    for (const name of ["capture.mic_hint", "capture.voice"]) {
      expect(canFlip(r("admin"), name)).toBe(true);
      expect(canFlip(r("infosec"), name)).toBe(true);
      expect(canFlip(r("hr"), name)).toBe(false);
    }
    expect(canFlip(r("infosec"), "speech.hosted")).toBe(true);
    expect(canFlip(r("admin"), "speech.hosted")).toBe(false);
  });
});

describe("shared policy file", () => {
  it("rbac.json matches policy/rbac.yaml exactly; run `npm run sync:shared`", () => {
    const yaml = parse(readFileSync(path.resolve(__dirname, "../../../../policy/rbac.yaml"), "utf8"));
    expect(policyJson).toEqual(yaml);
  });
});

describe("canFlip with names that are not switches (BLD-A171 review)", () => {
  it("refuses built-in object keys instead of throwing", () => {
    const admin = new Set(["admin", "infosec"]);
    for (const name of ["constructor", "__proto__", "toString", "hasOwnProperty"]) {
      expect(() => canFlip(admin, name)).not.toThrow();
      expect(canFlip(admin, name)).toBe(false);
    }
  });
});
