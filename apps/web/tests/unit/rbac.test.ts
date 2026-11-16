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
];
const SECTION_3_1: Record<string, string[]> = {
  submit: ALL,
  see_org_ideas: ALL,
  see_committee_only_ideas: ALL,
  work_review_queue: ["reviewer", "admin"],
  view_review_queue: ["reviewer", "core_committee", "admin"],
  veto_desk_decision: ["core_committee"],
  propose_rule_changes: ["reviewer", "admin"],
  approve_scorecard_changes: ["core_committee"],
  open_attachments: ALL,
  see_restored_values: ALL,
  approve_handover: ["sponsor"],
  reveal_identity: ["admin"],
  grant_roles: ["admin"],
};

describe("policy agrees with ARCHITECTURE §3.1", () => {
  it("lists exactly the eight §3.1 role columns", () => {
    expect([...ROLE_COLUMNS]).toEqual(ALL);
  });

  for (const [capability, allowed] of Object.entries(SECTION_3_1)) {
    it(capability, () => {
      const actual = ALL.filter((role) => can(rolesOf(role), capability));
      expect(actual).toEqual(allowed);
    });
  }

  it("keeps the scope words the handlers must enforce", () => {
    expect(scopesFor(rolesOf("lob_committee"), "see_committee_only_ideas")).toEqual(["own", "own_lob"]);
    expect(scopesFor(rolesOf("admin"), "reveal_identity")).toEqual(["with_reason_logged"]);
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

describe("navigation and pages (AT-B2-06)", () => {
  const labels = (role: string) => navFor(rolesOf(role)).map((n) => n.label);
  const base = ["Share an idea", "My ideas", "Wall", "Messages"];
  it("everyone gets Share an idea, My ideas, Wall and Messages", () =>
    expect(labels("contributor")).toEqual(base));
  it("review desk adds Review", () => expect(labels("reviewer")).toEqual([...base, "Review"]));
  it("core committee adds Desk decisions, Ones, Delivery and Lenses", () =>
    expect(labels("core_committee")).toEqual([...base, "Desk decisions", "Ones", "Delivery", "Lenses"]));
  it("admin adds Ones, Delivery, Lenses and Admin", () =>
    expect(labels("admin")).toEqual([...base, "Ones", "Delivery", "Lenses", "Admin"]));
  it("the CEO adds Ones (DEC-042) and Delivery", () =>
    expect(labels("ceo")).toEqual([...base, "Ones", "Delivery"]));
  it("sponsors and working groups add Delivery; LOB committees add Lenses", () => {
    expect(labels("sponsor")).toEqual([...base, "Delivery"]);
    expect(labels("working_group")).toEqual([...base, "Delivery"]);
    expect(labels("lob_committee")).toEqual([...base, "Lenses"]);
  });
  it("with the committee flow on, Committee takes Desk decisions' place; LOB committees get it too (BLD-227)", () => {
    const on = new Set(["committee.flow"]);
    const withFlow = (role: string) => navFor(rolesOf(role), on).map((n) => n.label);
    expect(withFlow("core_committee")).toEqual([...base, "Committee", "Ones", "Delivery", "Lenses"]);
    expect(withFlow("lob_committee")).toEqual([...base, "Committee", "Lenses"]);
    expect(withFlow("contributor")).toEqual(base);
    expect(withFlow("admin")).toEqual([...base, "Ones", "Delivery", "Lenses", "Admin"]);
    expect(navFor(rolesOf("core_committee"), on).find((n) => n.label === "Committee")?.href).toBe(
      "/committee",
    );
    // Another switch does not count; with the flow paused core members keep their direct link.
    expect(navFor(rolesOf("core_committee"), new Set(["clusters.batch"])).map((n) => n.label)).toContain(
      "Desk decisions",
    );
  });
  it("only the committee flow pair is tied to a switch, each item by one rule", () => {
    const rules = policyJson.navigation as Array<{ when_on?: string; when_off?: string }>;
    for (const r of rules) expect(Boolean(r.when_on && r.when_off)).toBe(false);
    expect(rules.flatMap((r) => [r.when_on, r.when_off]).filter(Boolean)).toEqual([
      "committee.flow",
      "committee.flow",
    ]);
  });
  it("pages follow the same rules", () => {
    expect(canSeePage(rolesOf("contributor"), "/review")).toBe(false);
    expect(canSeePage(rolesOf("reviewer"), "/review")).toBe(true);
    expect(canSeePage(rolesOf("contributor"), "/admin")).toBe(false);
    expect(canSeePage(rolesOf("infosec"), "/admin")).toBe(true);
    // The committee page is for the core committee (scoring retired, DEC-106); LOB committees no longer open it.
    expect(canSeePage(rolesOf("core_committee"), "/committee")).toBe(true);
    expect(canSeePage(rolesOf("lob_committee"), "/committee")).toBe(false);
    expect(canSeePage(rolesOf("core_committee"), "/reports")).toBe(true);
    expect(canSeePage(rolesOf("contributor"), "/reports")).toBe(false);
    expect(canSeePage(rolesOf("contributor"), "/share")).toBe(true);
    expect(canSeePage(rolesOf("contributor"), "/ones/console")).toBe(false);
    expect(canSeePage(rolesOf("contributor"), "/ones/showcase/3")).toBe(false);
    expect(canSeePage(rolesOf("core_committee"), "/ones/console")).toBe(true);
    expect(canSeePage(rolesOf("contributor"), "/ones/leaderboard")).toBe(true); // the page itself says "Ones only"
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

  it("delivery, lenses and learning (BLD-115 to BLD-122)", () => {
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
    expect(decide(rolesOf("core_committee"), "GET", "/api/learning").kind).toBe("deny");
    expect(decide(rolesOf("admin"), "POST", "/api/learning/proposals/3/decide").kind).toBe("allow");
    expect(canSeePage(rolesOf("contributor"), "/delivery/4")).toBe(true); // their own, or not found
    expect(canSeePage(rolesOf("admin"), "/learning")).toBe(true);
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
