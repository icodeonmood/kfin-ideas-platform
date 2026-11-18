// @vitest-environment jsdom
/**
 * The admin page's confirm steps keep focus where a keyboard or screen-reader user expects it (WCAG 2.4.3; lane A,
 * BLD-A210; J-ONE steps 1 and 3, DEC-106): "Mark shipped", "Remove" a One and "Put back" on the Wall. Opening
 * moves focus into the step, Cancel brings it back to the button, and after success focus goes to the section's
 * heading, since the row has left the table. Also the S1 to S3 form: an empty share is refused before anything is
 * sent (L-AUDIT.flags, BLD-A216). Synthetic people only; fetch is a stub.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Flags, type Flag } from "@/app/admin/flags";
import { Programme, type ProgrammeView } from "@/app/admin/programme";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const REF = "IDEA-2026-000123";
const OFF = "IDEA-2026-000456";

const VIEW: ProgrammeView = {
  can: { programme: true, wall: true },
  off_wall: [
    {
      id: 7,
      idea_ref: OFF,
      title: "Branch queue tokens",
      by: "Tanvi Joshi",
      reason: "Names a customer's branch",
      at: "2026-11-17T10:00:00+05:30",
    },
  ],
  picked: [],
  being_built: [
    {
      idea_ref: REF,
      title: "Mandate checks",
      team: "Mandates crew",
      lead: "Kabir Sethi",
      since: "2026-11-10",
      since_label: "10 Nov",
    },
  ],
  shipped: [],
  due: [],
  entered: [],
  ones: [
    {
      id: 17,
      number: 17,
      tier: 2,
      founding: false,
      idea_ref: REF,
      name: "Arjun Pillai",
      email: "arjun.pillai@kfintech.example",
      since: "2026-11-12T10:00:00+05:30",
    },
  ],
  scale_nouns: ["branches"],
};
/** What the page reloads after each action: the row has gone. */
const AFTER: ProgrammeView = { ...VIEW, off_wall: [], being_built: [], ones: [] };

let host: HTMLElement;
let root: Root;
let calls: Array<{ method: string; url: string }>;

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      calls.push({ method: init.method ?? "GET", url });
      if (url === "/api/admin/programme") return Response.json(AFTER);
      return Response.json({});
    }),
  );
});

afterEach(async () => {
  await act(async () => root.unmount());
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
});

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
const button = (name: string) =>
  Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find((b) => text(b) === name);
const heading = (name: string) =>
  Array.from(document.querySelectorAll<HTMLHeadingElement>("h2")).find((h) => text(h) === name);
/** Focus and click, as a keyboard user's Enter would, then let the stubbed fetches and the reload settle. */
const click = async (el: HTMLElement | undefined) => {
  expect(el).toBeDefined();
  await act(async () => {
    el!.focus();
    el!.click();
    for (let i = 0; i < 5; i++) await new Promise((resolve) => setTimeout(resolve, 0));
  });
};

async function renderProgramme() {
  await act(async () => root.render(createElement(Programme, { initial: VIEW })));
}

describe("WCAG 2.4.3: focus in the admin page's confirm steps", () => {
  it("J-ONE/1 Mark shipped: focus into the question, back to the button on Cancel, to the heading after", async () => {
    await renderProgramme();
    await click(button(`Mark shipped: ${REF}`));
    const group = document.activeElement as HTMLElement;
    expect(group.getAttribute("role")).toBe("group");
    expect(group.getAttribute("aria-label")).toBe(`Mark ${REF} shipped`);
    expect(text(document.getElementById(group.getAttribute("aria-describedby")!))).toBe(
      "Is it live and in use?",
    );

    await click(button("Cancel"));
    expect(document.activeElement).toBe(button(`Mark shipped: ${REF}`));

    await click(button(`Mark shipped: ${REF}`));
    await click(button("Yes, it has shipped"));
    expect(calls).toContainEqual({ method: "POST", url: `/api/admin/ideas/${REF}/shipped` });
    expect(document.activeElement).toBe(heading("Being built: mark shipped"));
    expect(text(document.querySelector('[role="status"]'))).toBe(
      `${REF} is shipped. Its 30- and 90-day checks are set.`,
    );
  });

  it("J-ONE/3 Remove a One: focus into the question, back on Cancel, to The Ones heading after", async () => {
    await renderProgramme();
    await click(button("Remove: No. 17, Arjun Pillai"));
    const group = document.activeElement as HTMLElement;
    expect(group.getAttribute("aria-label")).toBe("Remove No. 17, Arjun Pillai");

    await click(button("Cancel"));
    expect(document.activeElement).toBe(button("Remove: No. 17, Arjun Pillai"));

    await click(button("Remove: No. 17, Arjun Pillai"));
    await click(button("Yes, remove"));
    expect(calls).toContainEqual({ method: "DELETE", url: "/api/admin/ones/17" });
    expect(document.activeElement).toBe(heading("The Ones"));
  });

  it("DEC-106 Put back: focus to the reason, back on Cancel, to the section heading after", async () => {
    await renderProgramme();
    await click(button(`Put back: ${OFF}`));
    expect(document.activeElement?.tagName).toBe("TEXTAREA");
    expect(text(document.querySelector(`label[for="${document.activeElement!.id}"]`))).toBe(
      "Reason for putting it back",
    );

    await click(button("Cancel"));
    expect(document.activeElement).toBe(button(`Put back: ${OFF}`));

    await click(button(`Put back: ${OFF}`));
    await click(button("Put back on the Wall"));
    expect(calls).toContainEqual({ method: "DELETE", url: `/api/admin/ideas/${OFF}/wall-removal` });
    expect(document.activeElement).toBe(heading("Take an idea off the Wall"));
  });
});

describe("L-AUDIT.flags: the experiment form", () => {
  const S1: Flag = {
    key: "s1",
    description: "The check screen shows the draft first.",
    state: "on",
    alternative_percent: 20,
    changed_at: "2026-11-17T10:00:00+05:30",
    people: [],
    exposures: { default: 4, alternative: 1 },
  };

  it("BLD-A216: an empty share is refused in the form, tied to the field, and nothing is sent", async () => {
    await act(async () => root.render(createElement(Flags, { initial: [S1] })));
    const share = document.querySelector<HTMLInputElement>("input[inputmode='numeric']")!;
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => {
      setValue.call(share, "");
      share.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await click(button("Save S1"));
    expect(calls).toEqual([]);
    expect(share.getAttribute("aria-invalid")).toBe("true");
    const err = document.getElementById(share.getAttribute("aria-describedby")!);
    expect(err?.getAttribute("role")).toBe("alert");
    expect(text(err)).toBe("Enter a whole number from 0 to 100.");
  });
});
