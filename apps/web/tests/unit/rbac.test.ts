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
  approve_cluster_proposals: ["reviewer", "admin"],
  propose_rule_changes: ["reviewer", "admin"],
  approve_scorecard_changes: ["core_committee"],
  see_core_briefs: ["core_committee"],
  present: ALL,
  open_attachments: ALL,
  see_restored_values: ALL,
  score: ["lob_committee", "core_committee"],
  decide: ["lob_committee", "core_committee"],
  hear_appeals: ["core_committee", "appeal_panel"],
  run_action_plans: ["working_group", "sponsor", "admin"],
  approve_handover: ["sponsor"],
  see_people_view: ALL,
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
    expect(decide(rolesOf("core_committee"), "POST", "/api/review/items/7/action").kind).toBe("deny");
    expect(decide(rolesOf("contributor"), "GET", "/api/review/items").kind).toBe("deny");
  });
});

describe("navigation and pages (AT-B2-06)", () => {
  const labels = (role: string) => navFor(rolesOf(role)).map((n) => n.label);
  const base = ["Share an idea", "My ideas", "Wall", "Messages"];
  it("everyone gets Share an idea, My ideas, Wall and Messages", () =>
    expect(labels("contributor")).toEqual(base));
  it("review desk adds Review", () => expect(labels("reviewer")).toEqual([...base, "Review"]));
  it("core committee adds Desk decisions", () =>
    expect(labels("core_committee")).toEqual([...base, "Desk decisions"]));
  it("admin adds Admin", () => expect(labels("admin")).toEqual([...base, "Admin"]));
  it("pages follow the same rules", () => {
    expect(canSeePage(rolesOf("contributor"), "/review")).toBe(false);
    expect(canSeePage(rolesOf("reviewer"), "/review")).toBe(true);
    expect(canSeePage(rolesOf("core_committee"), "/desk-decisions")).toBe(true);
    expect(canSeePage(rolesOf("contributor"), "/admin")).toBe(false);
    expect(canSeePage(rolesOf("contributor"), "/share")).toBe(true);
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
  });
});

describe("shared policy file", () => {
  it("rbac.json matches policy/rbac.yaml exactly; run `npm run sync:shared`", () => {
    const yaml = parse(readFileSync(path.resolve(__dirname, "../../../../policy/rbac.yaml"), "utf8"));
    expect(policyJson).toEqual(yaml);
  });
});
