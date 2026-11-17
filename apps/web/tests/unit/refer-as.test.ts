import { describe, expect, it } from "vitest";

import { switchesFor, UNGUARDED_WRITES } from "@/lib/killswitch-routes";
import policy from "@/lib/rbac.json";
import { parseReferAs, REFER_AS, storedReferAs, wireReferAs } from "@/lib/refer-as";

describe("BLD-C111 refer_as (DEC-108 (3), BLD-E010): she, he, they or unset", () => {
  it("accepts exactly the four wire values, and null as unset", () => {
    expect(REFER_AS).toEqual(["she", "he", "they", "unset"]);
    for (const v of REFER_AS) expect(parseReferAs(v)).toBe(v);
    expect(parseReferAs(null)).toBe("unset");
    for (const bad of ["She", "her", "", "female", 1, true, {}, undefined])
      expect(parseReferAs(bad)).toBeUndefined();
  });

  it("stores unset as NULL and reads anything else back as unset", () => {
    expect(storedReferAs("unset")).toBeNull();
    expect(storedReferAs("they")).toBe("they");
    expect(wireReferAs(null)).toBe("unset");
    expect(wireReferAs(undefined)).toBe("unset");
    expect(wireReferAs("he")).toBe("he");
    expect(wireReferAs("x")).toBe("unset");
  });

  it("is the signed-in person's own: signed_in for GET and PUT, and no switch pauses it", () => {
    const endpoints = (policy as { endpoints: string[] }).endpoints.map((l) =>
      l.split(/\s+/).slice(0, 3).join(" "),
    );
    expect(endpoints).toContain("GET /api/me/refer-as signed_in");
    expect(endpoints).toContain("PUT /api/me/refer-as signed_in");
    expect(switchesFor("PUT", "/api/me/refer-as")).toEqual([]);
    expect(UNGUARDED_WRITES.some((re) => re.test("/api/me/refer-as"))).toBe(true);
  });
});
