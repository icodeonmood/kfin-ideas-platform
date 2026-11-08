import { describe, expect, it } from "vitest";

import { restoreMode, type IdeaForView, type Viewer } from "@/server/restore";

const idea = (reviewItem: IdeaForView["reviewItem"] = null): IdeaForView => ({
  contributorCode: "CTR-a1b2c3",
  reviewItem,
});
const viewer = (roles: string[], code: string | null = "CTR-ffffff", id = "u-1"): Viewer => ({
  id,
  contributorCode: code,
  roles,
});

describe("restore on view (AT-B4-05)", () => {
  it("shows real values to the person whose idea it is", () => {
    expect(restoreMode(viewer(["contributor"], "CTR-a1b2c3"), idea())).toBe("real");
  });

  it("shows real values to the reviewer handling it, and neutral labels to other reviewers", () => {
    const assigned = idea({ assignedTo: "u-1", state: "in_progress" });
    expect(restoreMode(viewer(["contributor", "reviewer"]), assigned)).toBe("real");
    expect(restoreMode(viewer(["contributor", "reviewer"], null, "u-2"), assigned)).toBe("neutral");
    const queue = idea({ assignedTo: null, state: "open" });
    expect(restoreMode(viewer(["reviewer"], null, "u-2"), queue)).toBe("real");
    const decided = idea({ assignedTo: null, state: "decided" });
    expect(restoreMode(viewer(["reviewer"], null, "u-2"), decided)).toBe("neutral");
    expect(restoreMode(viewer(["reviewer"]), idea())).toBe("neutral"); // not on the desk yet
  });

  it("shows real values to the core committee", () => {
    expect(restoreMode(viewer(["core_committee"]), idea())).toBe("real");
  });

  it("gives admins real values only with a reason", () => {
    expect(restoreMode(viewer(["admin"]), idea())).toBe("neutral");
    expect(restoreMode(viewer(["admin"]), idea(), { adminReason: "Data subject request DSR-0042" })).toBe(
      "real",
    );
  });

  it("shows neutral labels to any other employee, including other committees for now", () => {
    for (const roles of [["contributor"], ["lob_committee"], ["working_group"], ["sponsor"], ["hr"]]) {
      expect(restoreMode(viewer(roles), idea())).toBe("neutral");
    }
  });
});
