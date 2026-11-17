/**
 * The sidebar's review-side sections (C-SIDEBAR.anatomy; S-R1.rules/5, S-R4.rules/4): the review desk's "Waiting on
 * sharers" and the Ones Committee's "Closing soonest", up to three each, from lane B's desk and committee reads.
 */
import { describe, expect, it } from "vitest";

import type { CommitteeRow } from "@/lib/contracts";
import { committeeRows, deskRows } from "@/server/shell";

function windowRow(id: string, state: CommitteeRow["window"]["state"], left: string | null): CommitteeRow {
  return {
    window_id: id,
    kind: "decision",
    idea: { id: `IDEA-2026-00140${id}`, title: `Idea ${id}`, meta: "" },
    window: { state, left } as CommitteeRow["window"],
  } as CommitteeRow;
}

describe("S-R1.rules/5: Waiting on sharers", () => {
  it("takes the desk's three most urgent with blue, amber as warn and red as bad", () => {
    const rows = deskRows({
      waiting_on_sharers: [
        { idea_id: "IDEA-2026-001481", title: "Rejection SMS codes need plain words", dot: "red" },
        { idea_id: "IDEA-2026-001470", title: "Branch queue times are not tracked", dot: "amber" },
        { idea_id: "IDEA-2026-001455", title: "Cheque scans need re-uploading", dot: "blue" },
        { idea_id: "IDEA-2026-001433", title: "Statements arrive after the SIP date", dot: "blue" },
      ],
    });
    expect(rows).toEqual([
      {
        href: "/desk/ideas/IDEA-2026-001481",
        title: "Rejection SMS codes need plain words",
        tone: "bad",
        words: "Overdue",
      },
      {
        href: "/desk/ideas/IDEA-2026-001470",
        title: "Branch queue times are not tracked",
        tone: "warn",
        words: "Under a day left",
      },
      {
        href: "/desk/ideas/IDEA-2026-001455",
        title: "Cheque scans need re-uploading",
        tone: "blue",
        words: "Waiting on the sharer",
      },
    ]);
  });

  it("is empty when the desk could not be read in time", () => {
    expect(deskRows(null)).toEqual([]);
  });
});

describe("S-R4.rules/4: Closing soonest", () => {
  it("takes the first three open windows, each opening its row in place", () => {
    const rows = committeeRows({
      items: [
        windowRow("1", "open", "3 days left"),
        windowRow("2", "reversed", null),
        windowRow("3", "extended", "17 days left"),
        windowRow("4", "open", "22 days left"),
        windowRow("5", "open", "24 days left"),
      ],
    });
    expect(rows.map((r) => [r.href, r.title, r.meta, r.tone])).toEqual([
      ["/committee?open=1", "Idea 1", "3 days left", "blue"],
      ["/committee?open=3", "Idea 3", "17 days left", "blue"],
      ["/committee?open=4", "Idea 4", "22 days left", "blue"],
    ]);
    expect(committeeRows(null)).toEqual([]);
  });
});
