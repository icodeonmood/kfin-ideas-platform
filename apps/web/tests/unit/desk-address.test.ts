import { describe, expect, it } from "vitest";

import { addressBack, deskHref, deskSearchBody, deskUrlState, type DeskList } from "@/lib/desk/address";

describe("S-R1.rules/4, J-BROWSE/4, DEC-110: the desk's tab and sort live in its address, its search never does", () => {
  it("S-R1.rules/4 DEC-110 reads the tab and sort an address names, null for any it does not, and never a search", () => {
    const got = deskUrlState("?tab=decided&sort=area&q=sms");
    expect(got).toEqual({ tab: "decided", sort: "area", row: null, dy: null });
    expect(got).not.toHaveProperty("q");
    expect(deskUrlState("")).toEqual({ tab: null, sort: null, row: null, dy: null });
    expect(deskUrlState("?tab=bogus&sort=newest")).toMatchObject({ tab: null, sort: null });
  });

  it("S-R1.rules/4 DEC-110 writes tab and sort always and the search never: its words go in a request body", () => {
    expect(deskHref({ tab: "waiting", sort: "time_left" })).toBe("/desk?tab=waiting&sort=time_left");
    const searched: DeskList = { tab: "to_review", sort: "decide_by", q: "rejection sms" };
    const href = deskHref(searched);
    expect(href).toBe("/desk?tab=to_review&sort=decide_by");
    expect(href).not.toMatch(/rejection|sms|q=/);
    expect(JSON.parse(deskSearchBody(searched))).toEqual({
      tab: "to_review",
      sort: "decide_by",
      q: "rejection sms",
    });
  });
});

describe("S-R1.rules/4, J-BROWSE/4: Back restores the opened row", () => {
  it("S-R1.rules/4 the row opened and its offset follow the list's own state in the address", () => {
    const list: DeskList = { tab: "waiting", sort: "decide_by", q: "kyc" };
    const href = deskHref(list, "8c1e2f4a-row", 312.6);
    expect(href).toBe("/desk?tab=waiting&sort=decide_by&row=8c1e2f4a-row&dy=313");
    expect(deskUrlState(href.slice("/desk".length))).toEqual({
      tab: "waiting",
      sort: "decide_by",
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
    expect(deskHref({ tab: "waiting", sort: "area" }, undefined, 40)).toBe("/desk?tab=waiting&sort=area");
  });
});

describe("S-R1.rules/4: a list that could not be read leaves the page consistent", () => {
  const shown = { tab: "waiting", sort: "time_left", q: "" } as const;

  it("S-R1.rules/4 the address goes back to the list still on screen after a tab or sort that failed", () => {
    expect(addressBack(shown, { ...shown, tab: "decided" })).toBe("/desk?tab=waiting&sort=time_left");
    expect(addressBack(shown, { ...shown, sort: "area" })).toBe("/desk?tab=waiting&sort=time_left");
    expect(addressBack({ ...shown, q: "sms" }, { ...shown, tab: "decided", q: "kyc" })).toBe(
      "/desk?tab=waiting&sort=time_left",
    );
  });

  it("S-R1.rules/4 DEC-110 nothing to put back in the address when only the search failed: the address never had it", () => {
    expect(addressBack(shown, { ...shown })).toBeNull();
    expect(addressBack({ ...shown, q: "sms" }, { ...shown, q: "kyc" })).toBeNull();
  });
});
