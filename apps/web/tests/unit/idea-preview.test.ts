// @vitest-environment jsdom
/**
 * C-PREVIEW, the preview pop-up for someone else's idea (BLD-C100 to BLD-C103): both views, focus in, trapped and
 * back to the opener, Escape, the cross and the backdrop, the footer button's hand-over, primaryDone, the reviewer's
 * comparison rows, and the fetch of GET /api/ideas/:id/preview against mocked responses. Synthetic people only: the
 * pack's fictional cast.
 */
import { act, createElement, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  IdeaPreviewDialog,
  PREVIEW_COPY,
  previewUrl,
  sharedOn,
  type IdeaPreviewDialogProps,
} from "@/components/preview/idea-preview";
import type { IdeaPreview } from "@/lib/contracts";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const RAVI: IdeaPreview = {
  id: "IDEA-2026-001412",
  title: "Rejection SMS codes confuse investors",
  status: "with_review_desk",
  area: "Investor service",
  city: "Hyderabad",
  shared_at: "2026-11-02T10:30:00+05:30",
  lead: { id: "p-ravi", name: "Ravi Nair", first_name: "Ravi", initials: "RN" },
  crew_faces: [
    { id: "p-ravi", name: "Ravi Nair", first_name: "Ravi", initials: "RN" },
    { id: "p-aditi", name: "Aditi Sharma", first_name: "Aditi", initials: "AS" },
    { id: "p-prakash", name: "Prakash Kumar", first_name: "Prakash", initials: "PK" },
  ],
  crew_count: 4,
  in_their_words: "Investors get a code, not a reason, and then they call us.",
  looking_for: "Someone who takes these calls at a branch every day.",
  hue: 1,
  compare: {
    often: "About 25 calls a day, Hyderabad",
    who: "Investors, branch staff",
    worth: "60 to 90 hours a month",
  },
};

const KAVYA_ID = "IDEA-2026-001481";
/** What the route adds for a reviewer with `?compare_with=` (A-API.idea-preview, BLD-C090 on c/similar). */
const NEXT_TO_KAVYA: NonNullable<IdeaPreview["compare_with"]> = {
  id: KAVYA_ID,
  title: "Investors call to ask why a redemption was rejected",
  owner: { id: "p-kavya", name: "Kavya Iyer", first_name: "Kavya", initials: "KI" },
  often: "About 40 calls a day, one branch",
  who: "Investors, KFin teams",
};
/** The reviewer's response: `compare` and `compare_with` side by side. */
const RAVI_FOR_DESK: IdeaPreview = { ...RAVI, compare_with: NEXT_TO_KAVYA };

let host: HTMLElement;
let root: Root;

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  document.body.innerHTML = "";
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const dialog = () => document.querySelector<HTMLElement>('[role="dialog"]');
const buttonNamed = (name: string) =>
  Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find(
    (b) => (b.getAttribute("aria-label") ?? b.textContent) === name,
  );
const textOf = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();

async function render(props: Partial<IdeaPreviewDialogProps> = {}) {
  const onClose = vi.fn();
  const all: IdeaPreviewDialogProps = {
    ideaId: RAVI.id,
    view: "sharer",
    open: true,
    onClose,
    preview: RAVI,
    ...props,
  };
  await act(async () => root.render(createElement(IdeaPreviewDialog, all)));
  return { onClose };
}

/** A page with a "Preview" button that opens the pop-up, as a caller would wire it. */
function Harness(props: Partial<IdeaPreviewDialogProps> & { log: string[] }) {
  const { log, ...rest } = props;
  const [open, setOpen] = useState(false);
  return createElement(
    "main",
    null,
    createElement("button", { type: "button", id: "opener", onClick: () => setOpen(true) }, "Preview"),
    createElement(IdeaPreviewDialog, {
      ideaId: RAVI.id,
      view: "sharer",
      preview: RAVI,
      ...rest,
      open,
      onClose: () => {
        log.push("close");
        setOpen(false);
      },
    }),
  );
}

async function openFromHarness(props: Partial<IdeaPreviewDialogProps> = {}, log: string[] = []) {
  await act(async () => root.render(createElement(Harness, { ...props, log })));
  const opener = document.getElementById("opener") as HTMLButtonElement;
  opener.focus();
  await act(async () => opener.click());
  return { log, opener };
}

async function press(key: string, init: KeyboardEventInit = {}) {
  const target = (document.activeElement as HTMLElement | null) ?? document.body;
  await act(async () => {
    target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...init }));
  });
}

function json(body: unknown, status = 200) {
  return Promise.resolve({ ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) });
}

describe("C-PREVIEW dialog (BLD-C100)", () => {
  it("BLD-C100 C-PREVIEW.behaviour/4: renders nothing when closed, and at the page root (a portal) when open", async () => {
    await render({ open: false });
    expect(dialog()).toBeNull();

    await render({ open: true });
    const d = dialog();
    expect(d).not.toBeNull();
    expect(host.contains(d)).toBe(false);
    expect(d!.closest(".pvwrap")!.parentElement).toBe(document.body);
  });

  it("BLD-C100: role=dialog, aria-modal, labelled by the title; the cross is 'Close the preview'", async () => {
    await render();
    const d = dialog()!;
    expect(d.getAttribute("aria-modal")).toBe("true");
    const title = document.getElementById(d.getAttribute("aria-labelledby")!);
    expect(title?.tagName).toBe("H2");
    expect(textOf(title)).toBe(RAVI.title);
    expect(buttonNamed("Close the preview")).toBeDefined();
    expect(PREVIEW_COPY.close).toBe("Close the preview");
  });

  it("BLD-C100 C-PREVIEW.behaviour/2: focus moves inside on open and returns to the opener on close", async () => {
    const { log, opener } = await openFromHarness();
    expect(document.activeElement).toBe(dialog());

    await press("Escape");
    expect(log).toEqual(["close"]);
    expect(dialog()).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it("BLD-C100: Tab and Shift+Tab stay inside the pop-up", async () => {
    await openFromHarness({ onPrimary: () => undefined });
    const close = buttonNamed("Close the preview")!;
    const teamUp = buttonNamed(`Team up on ${RAVI.title}`)!;

    // From the dialog itself, Shift+Tab goes to the last control.
    await press("Tab", { shiftKey: true });
    expect(document.activeElement).toBe(teamUp);
    // From the last control, Tab wraps to the first.
    await press("Tab");
    expect(document.activeElement).toBe(close);
    // From the first, Shift+Tab wraps to the last.
    await press("Tab", { shiftKey: true });
    expect(document.activeElement).toBe(teamUp);
  });

  it("BLD-C100: focus that lands outside is brought back in", async () => {
    const { opener } = await openFromHarness();
    await act(async () => opener.focus());
    expect(dialog()!.contains(document.activeElement)).toBe(true);
  });

  it("BLD-C100: Escape, the cross and a click on the backdrop each close it; a click inside does not", async () => {
    let r = await render();
    await press("Escape");
    expect(r.onClose).toHaveBeenCalledTimes(1);

    await act(async () => root.render(createElement("div")));
    r = await render();
    await act(async () => buttonNamed("Close the preview")!.click());
    expect(r.onClose).toHaveBeenCalledTimes(1);

    await act(async () => root.render(createElement("div")));
    r = await render();
    await act(async () => (document.querySelector(".pvsec") as HTMLElement).click());
    expect(r.onClose).not.toHaveBeenCalled();
    await act(async () => (document.querySelector(".pvback") as HTMLElement).click());
    expect(r.onClose).toHaveBeenCalledTimes(1);
  });

  it("BLD-C100 BLD-E005 F-MOTION: leaves on the Web Animations API, and at once with reduced motion", async () => {
    const animate = vi.fn(() => ({ finished: Promise.resolve() }) as unknown as Animation);
    Object.defineProperty(HTMLElement.prototype, "animate", { value: animate, configurable: true });
    try {
      vi.stubGlobal("matchMedia", (q: string) => ({ matches: false, media: q }));
      let r = await render();
      await act(async () => buttonNamed("Close the preview")!.click());
      expect(animate).toHaveBeenCalled();
      expect(r.onClose).toHaveBeenCalledTimes(1);

      animate.mockClear();
      await act(async () => root.render(createElement("div")));
      vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("reduce"), media: q }));
      r = await render();
      await act(async () => buttonNamed("Close the preview")!.click());
      expect(animate).not.toHaveBeenCalled();
      expect(r.onClose).toHaveBeenCalledTimes(1);
    } finally {
      delete (HTMLElement.prototype as { animate?: unknown }).animate;
    }
  });
});

describe("C-PREVIEW sharer view (BLD-C101)", () => {
  it("BLD-C101 C-PREVIEW.anatomy: band, why it matches, their words, they're looking for, crew, note, footer", async () => {
    await render({
      matchReason: "Close match: the same R07 SMS and the same calls",
      onPrimary: () => undefined,
    });
    const d = dialog()!;
    expect(textOf(d.querySelector(".pvband .pill"))).toBe("With the review desk");
    expect(textOf(d.querySelector(".pvref"))).toBe("IDEA-2026-001412");
    expect(textOf(d.querySelector(".pvmeta"))).toBe("Investor service, Hyderabad");
    expect(d.querySelector(".pvband")!.classList.contains("hue1")).toBe(true);
    expect(textOf(d.querySelector(".pvwhy"))).toBe("Close match: the same R07 SMS and the same calls");

    const labels = Array.from(d.querySelectorAll(".pvl")).map(textOf);
    expect(labels).toEqual(["The problem, in their words", "They’re looking for"]);
    const answers = Array.from(d.querySelectorAll(".pva")).map(textOf);
    expect(answers).toEqual([RAVI.in_their_words, RAVI.looking_for]);

    expect(textOf(d.querySelector(".pvcrew"))).toContain("Ravi Nair leads it, 4 on its crew");
    expect(Array.from(d.querySelectorAll(".pvav")).map((f) => f.getAttribute("aria-label"))).toEqual([
      "Ravi Nair",
      "Aditi Sharma",
      "Prakash Kumar",
    ]);
    expect(textOf(d.querySelector(".pvnote"))).toBe(
      "Teaming up adds you to their crew. Your draft stays yours.",
    );

    const full = d.querySelector<HTMLAnchorElement>("a.pvfull")!;
    expect(textOf(full)).toBe("Open the full idea");
    expect(full.getAttribute("href")).toBe("/ideas/IDEA-2026-001412");
    const teamUp = buttonNamed(`Team up on ${RAVI.title}`)!;
    expect(textOf(teamUp)).toBe("Team up");
    // Exactly one button in the footer, and no reviewer parts.
    expect(d.querySelectorAll(".pvf button")).toHaveLength(1);
    expect(d.textContent).not.toContain("Merge");
    expect(d.querySelector('[role="table"]')).toBeNull();
  });

  it("BLD-C101: on Status the note says 'Your idea stays yours.'; with no reason there is no blue line", async () => {
    await render({ yours: "idea" });
    expect(textOf(dialog()!.querySelector(".pvnote"))).toBe(
      "Teaming up adds you to their crew. Your idea stays yours.",
    );
    expect(dialog()!.querySelector(".pvwhy")).toBeNull();
  });

  it("BLD-C101 non-negotiable 7: the sharer's view never shows the reviewers' comparison, even if sent", async () => {
    await render({ preview: RAVI_FOR_DESK, compareWith: { name: "Kavya" }, compareWithId: KAVYA_ID });
    const d = dialog()!;
    expect(d.querySelector('[role="table"]')).toBeNull();
    expect(d.textContent).not.toContain("Next to");
    expect(d.textContent).not.toContain(RAVI.compare!.worth!);
    expect(d.textContent).not.toContain(NEXT_TO_KAVYA.often!);
  });

  it("BLD-C101 C-PREVIEW.behaviour/3: Team up closes the preview first, then hands the idea to the caller", async () => {
    const log: string[] = [];
    await openFromHarness({ onPrimary: (id: string) => void log.push(`primary:${id}`) }, log);
    await act(async () => buttonNamed(`Team up on ${RAVI.title}`)!.click());
    expect(log).toEqual(["close", "primary:IDEA-2026-001412"]);
    expect(dialog()).toBeNull();
  });

  it("BLD-C101: primaryDone replaces the button with a green status", async () => {
    await render({ onPrimary: () => undefined, primaryDone: "Waiting for Ravi" });
    const d = dialog()!;
    expect(buttonNamed(`Team up on ${RAVI.title}`)).toBeUndefined();
    expect(d.querySelectorAll(".pvf button")).toHaveLength(0);
    const done = d.querySelector('.pvf [role="status"]');
    expect(textOf(done)).toBe("Waiting for Ravi");
    expect(done!.classList.contains("pvok")).toBe(true);
  });
});

describe("C-PREVIEW reviewer view (BLD-C102)", () => {
  it("BLD-C102 C-PREVIEW.anatomy/4: 'Next to Kavya’s', three rows, one column per idea, and Merge", async () => {
    await render({
      view: "reviewer",
      preview: RAVI_FOR_DESK,
      compareWith: { name: "Kavya" },
      onPrimary: () => undefined,
    });
    const d = dialog()!;
    expect(textOf(d.querySelector(".pvmeta"))).toBe("Investor service, Hyderabad. Shared 2 November");
    const labels = Array.from(d.querySelectorAll(".pvl")).map(textOf);
    expect(labels).toEqual(["The problem, in Ravi’s words", "Next to Kavya’s"]);

    const table = d.querySelector('[role="table"]')!;
    expect(table.getAttribute("aria-label")).toBe("Ravi’s idea next to Kavya’s");
    const rows = Array.from(table.querySelectorAll('[role="row"]')).map((r) =>
      Array.from(r.children).map(textOf),
    );
    expect(rows).toEqual([
      ["Part", "Ravi’s", "Kavya’s"],
      ["How often", "About 25 calls a day, Hyderabad", "About 40 calls a day, one branch"],
      ["Who it affects", "Investors, branch staff", "Investors, KFin teams"],
      ["What it’s worth", "60 to 90 hours a month", "Not given"],
    ]);
    expect(table.querySelectorAll('[role="rowheader"]')).toHaveLength(3);
    expect(table.querySelectorAll('[role="cell"]')).toHaveLength(6);

    const merge = buttonNamed(`Merge with ${RAVI.title}`)!;
    expect(textOf(merge)).toBe("Merge");
    expect(d.textContent).not.toContain("Team up");
    expect(d.textContent).not.toContain("They’re looking for");
    expect(d.querySelector(".pvnote")).toBeNull();
  });

  it("BLD-C102: Merge closes first, then the caller opens C-SHEET-MERGE; afterwards 'Merged' shows", async () => {
    const log: string[] = [];
    await openFromHarness(
      {
        view: "reviewer",
        preview: RAVI_FOR_DESK,
        compareWith: { name: "Kavya" },
        onPrimary: (id: string) => void log.push(`merge:${id}`),
      },
      log,
    );
    await act(async () => buttonNamed(`Merge with ${RAVI.title}`)!.click());
    expect(log).toEqual(["close", "merge:IDEA-2026-001412"]);

    await render({ view: "reviewer", compareWith: { name: "Kavya" }, primaryDone: "Merged" });
    expect(textOf(dialog()!.querySelector('.pvf [role="status"]'))).toBe("Merged");
  });

  it("BLD-C102: without the caller's name, 'Next to' takes the first name of compare_with's owner", async () => {
    await render({ view: "reviewer", preview: RAVI_FOR_DESK });
    const d = dialog()!;
    expect(textOf(d.querySelector(".pvcmp .pvl"))).toBe("Next to Kavya’s");
    expect(d.querySelector('[role="table"]')!.getAttribute("aria-label")).toBe("Ravi’s idea next to Kavya’s");
  });

  it("BLD-C102: a missing value reads 'Not given'; no comparison without someone to compare with", async () => {
    await render({
      view: "reviewer",
      preview: { ...RAVI, compare: undefined },
      compareWith: { name: "Kavya" },
    });
    const cells = Array.from(dialog()!.querySelectorAll('[role="cell"]')).map(textOf);
    expect(cells).toEqual(Array(6).fill("Not given"));

    await act(async () => root.render(createElement("div")));
    await render({ view: "reviewer" });
    expect(dialog()!.querySelector('[role="table"]')).toBeNull();
  });
});

describe("C-PREVIEW data, A-API.idea-preview (BLD-C103)", () => {
  it("BLD-C103: builds GET /api/ideas/:id/preview, with ?compare_with= when given", () => {
    expect(previewUrl("IDEA-2026-001412")).toBe("/api/ideas/IDEA-2026-001412/preview");
    expect(previewUrl("IDEA-2026-001412", KAVYA_ID)).toBe(
      "/api/ideas/IDEA-2026-001412/preview?compare_with=IDEA-2026-001481",
    );
    expect(previewUrl("a/b")).toBe("/api/ideas/a%2Fb/preview");
    expect(sharedOn("2026-11-02T10:30:00+05:30")).toBe("2 November");
    expect(sharedOn("not a date")).toBe("");
  });

  it("BLD-C103: fetches the preview when none is passed; busy while it loads", async () => {
    let resolve: (v: unknown) => void = () => undefined;
    const fetchMock = vi.fn(() => new Promise((r) => (resolve = r)));
    vi.stubGlobal("fetch", fetchMock);

    await render({ preview: undefined });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String((fetchMock.mock.calls[0] as unknown[])[0])).toBe("/api/ideas/IDEA-2026-001412/preview");
    const d = dialog()!;
    expect(d.getAttribute("aria-busy")).toBe("true");
    expect(textOf(document.getElementById(d.getAttribute("aria-labelledby")!))).toBe("Loading the idea");

    await act(async () => resolve(await json(RAVI)));
    expect(d.getAttribute("aria-busy")).toBeNull();
    expect(textOf(document.getElementById(d.getAttribute("aria-labelledby")!))).toBe(RAVI.title);
  });

  it("BLD-C103: does not fetch when the caller passes the preview", async () => {
    const fetchMock = vi.fn(() => json(RAVI));
    vi.stubGlobal("fetch", fetchMock);
    await render();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("BLD-C103: reviewer with compareWithId: one fetch with ?compare_with=, both columns from its response", async () => {
    const fetchMock = vi.fn(() => json(RAVI_FOR_DESK));
    vi.stubGlobal("fetch", fetchMock);
    await render({ view: "reviewer", preview: undefined, compareWithId: KAVYA_ID });
    await act(async () => undefined);

    expect(fetchMock.mock.calls.map((c) => (c as unknown[])[0])).toEqual([
      `/api/ideas/IDEA-2026-001412/preview?compare_with=${KAVYA_ID}`,
    ]);
    const rows = Array.from(dialog()!.querySelectorAll('[role="row"]')).map((r) =>
      Array.from(r.children).map(textOf),
    );
    expect(rows).toEqual([
      ["Part", "Ravi’s", "Kavya’s"],
      ["How often", "About 25 calls a day, Hyderabad", "About 40 calls a day, one branch"],
      ["Who it affects", "Investors, branch staff", "Investors, KFin teams"],
      ["What it’s worth", "60 to 90 hours a month", "Not given"],
    ]);
  });

  it("BLD-C103: a failed load says so, and Try again fetches again", async () => {
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(json({ error: "not_found" }, 404))
      .mockReturnValue(json(RAVI));
    vi.stubGlobal("fetch", fetchMock);
    await render({ preview: undefined });
    await act(async () => undefined);

    const d = dialog()!;
    expect(textOf(document.getElementById(d.getAttribute("aria-labelledby")!))).toBe(
      "This idea did not load",
    );
    expect(textOf(d.querySelector('[role="alert"]'))).toBe("Check your connection, then try again.");
    await act(async () => buttonNamed("Try again")!.click());
    await act(async () => undefined);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(textOf(document.getElementById(d.getAttribute("aria-labelledby")!))).toBe(RAVI.title);
  });

  it("BLD-C103: Try again shows the loading state until the new fetch settles", async () => {
    let settle: (r: Response) => void = () => undefined;
    const pending = new Promise<Response>((resolve) => (settle = resolve));
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(json({ error: "not_found" }, 404))
      .mockReturnValueOnce(pending);
    vi.stubGlobal("fetch", fetchMock);
    await render({ preview: undefined });
    await act(async () => undefined);

    const d = dialog()!;
    await act(async () => buttonNamed("Try again")!.click());
    expect(textOf(document.getElementById(d.getAttribute("aria-labelledby")!))).toBe("Loading the idea");
    await act(async () => settle(await json(RAVI)));
    await act(async () => undefined);
    expect(textOf(document.getElementById(d.getAttribute("aria-labelledby")!))).toBe(RAVI.title);
  });

  it("BLD-C103 non-negotiable 7: a body that is not an IdeaPreview is not shown", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => json({ id: RAVI.id, own_words: "raw words" })),
    );
    await render({ preview: undefined });
    await act(async () => undefined);
    expect(dialog()!.textContent).not.toContain("raw words");
    expect(textOf(dialog()!.querySelector("h2"))).toBe("This idea did not load");
  });
});

describe("C-PREVIEW words (BLD-E008)", () => {
  it("BLD-E008: no gendered pronoun for a real person in any of the pop-up's words", async () => {
    const pronoun = /\b(he|she|him|her|his|hers|himself|herself)\b/i;
    const strings = Object.values(PREVIEW_COPY).flatMap((v) =>
      typeof v === "string"
        ? [v]
        : typeof v === "function"
          ? [(v as (a: string, b: string) => string)("Ravi", "Kavya")]
          : Object.values(v),
    );
    for (const s of strings) expect(s).not.toMatch(pronoun);

    await render({ matchReason: "Same R07 SMS as yours", onPrimary: () => undefined });
    expect(dialog()!.textContent).not.toMatch(pronoun);
    await act(async () => root.render(createElement("div")));
    await render({ view: "reviewer", preview: RAVI_FOR_DESK, onPrimary: () => undefined });
    expect(dialog()!.textContent).not.toMatch(pronoun);
  });
});
