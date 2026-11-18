import { describe, expect, it } from "vitest";

import { deskHref, deskUrlState } from "@/lib/desk/address";

describe("S-R1.rules/4, J-BROWSE/4: the desk's tab, sort and search live in its address", () => {
  it("S-R1.rules/4 reads the tab, sort and search an address names, and null for any it does not", () => {
    expect(deskUrlState("?tab=decided&sort=area&q=sms")).toMatchObject({
      tab: "decided",
      sort: "area",
      q: "sms",
    });
    expect(deskUrlState("")).toEqual({ tab: null, sort: null, q: "", row: null, dy: null });
    expect(deskUrlState("?tab=bogus&sort=newest")).toMatchObject({ tab: null, sort: null });
    expect(deskUrlState(`?q=${"a".repeat(250)}`).q).toHaveLength(200);
  });

  it("S-R1.rules/4 writes tab and sort always, the search only when there is one", () => {
    expect(deskHref({ tab: "waiting", sort: "time_left", q: "" })).toBe("/desk?tab=waiting&sort=time_left");
    expect(deskHref({ tab: "to_review", sort: "decide_by", q: "rejection sms" })).toBe(
      "/desk?tab=to_review&sort=decide_by&q=rejection+sms",
    );
  });
});

describe("S-R1.rules/4, J-BROWSE/4: Back restores the opened row", () => {
  it("S-R1.rules/4 the row opened and its offset follow the list's own state in the address", () => {
    const href = deskHref({ tab: "waiting", sort: "decide_by", q: "" }, "8c1e2f4a-row", 312.6);
    expect(href).toBe("/desk?tab=waiting&sort=decide_by&row=8c1e2f4a-row&dy=313");
    expect(deskUrlState(href.slice("/desk".length))).toEqual({
      tab: "waiting",
      sort: "decide_by",
      q: "",
      row: "8c1e2f4a-row",
      dy: 313,
    });
  });

  it("S-R1.rules/4 an offset above the window's top survives; one without a row, or not a number, is dropped", () => {
    expect(deskUrlState("?row=r1&dy=-40")).toMatchObject({ row: "r1", dy: -40 });
    expect(deskUrlState("?dy=200")).toMatchObject({ row: null, dy: null });
    expect(deskUrlState("?row=r1&dy=far")).toMatchObject({ row: "r1", dy: null });
    expect(deskUrlState("?row=r1")).toMatchObject({ row: "r1", dy: null });
    expect(deskUrlState("?row=&dy=10")).toMatchObject({ row: null, dy: null });
    expect(deskHref({ tab: "waiting", sort: "area", q: "" }, undefined, 40)).toBe(
      "/desk?tab=waiting&sort=area",
    );
  });
});
