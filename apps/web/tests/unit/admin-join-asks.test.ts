// @vitest-environment jsdom
/**
 * S-ADMIN, J-ONE step 1, L-DECIDE.rules/6 (DEC-111, BLD-A226): the admin page's "choose the build team" form shows
 * who asked to join the chosen idea's build team, oldest first, as a real list; an idea nobody asked about says so.
 * The worker sends names only, so the admin adds an asker by work email in the form's existing fields. Synthetic
 * people only; fetch is a stub.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Programme, type ProgrammeView } from "@/app/admin/programme";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const ASKED = "IDEA-2026-000123";
const QUIET = "IDEA-2026-000124";

const VIEW: ProgrammeView = {
  can: { programme: true, wall: false },
  off_wall: [],
  picked: [
    {
      idea_ref: ASKED,
      title: "Mandate checks",
      team: null,
      lead: null,
      since: "2026-11-11T10:00:00+05:30",
      since_label: "11 Nov 2026",
      asked_to_join: [
        {
          user_id: "0b7e6a52-6c1a-4e0e-8f43-000000000001",
          name: "Tanvi Rao",
          asked_at: "2026-11-12T09:30:00+05:30",
          asked_label: "12 Nov 2026",
        },
        {
          user_id: "0b7e6a52-6c1a-4e0e-8f43-000000000002",
          name: "Kabir Sethi",
          asked_at: "2026-11-17T23:10:00+05:30",
          asked_label: "17 Nov 2026",
        },
      ],
    },
    {
      idea_ref: QUIET,
      title: "Branch queue tokens",
      team: null,
      lead: null,
      since: null,
      since_label: null,
      asked_to_join: [],
    },
  ],
  being_built: [],
  shipped: [],
  due: [],
  entered: [],
  ones: [],
  scale_nouns: [],
};

let host: HTMLElement;
let root: Root;

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({})),
  );
});

afterEach(async () => {
  await act(async () => root.unmount());
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
});

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();

async function render(view: ProgrammeView = VIEW) {
  await act(async () => root.render(createElement(Programme, { initial: view })));
}

/** The "Asked to join" heading and the list it names. */
function asked() {
  const heading = Array.from(document.querySelectorAll("h4")).find((h) => text(h) === "Asked to join");
  const list = heading ? document.querySelector(`ul[aria-labelledby="${heading.id}"]`) : null;
  return { heading, items: list ? Array.from(list.querySelectorAll("li")).map(text) : null };
}

async function chooseIdea(ref: string) {
  const select = document.querySelector<HTMLSelectElement>("form select");
  expect(select).not.toBeNull();
  await act(async () => {
    select!.value = ref;
    select!.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

describe("S-ADMIN J-ONE/1 L-DECIDE/6: who asked to join the build team", () => {
  it("lists the askers of the chosen idea, oldest first, inside the build-team form", async () => {
    await render();
    const { heading, items } = asked();
    expect(heading?.closest("form")).not.toBeNull();
    expect(items).toEqual(["Tanvi Rao, asked 12 Nov 2026", "Kabir Sethi, asked 17 Nov 2026"]);
    expect(document.body.textContent).not.toContain("No one has asked to join yet.");
  });

  it("follows the idea being chosen, and says when no one has asked", async () => {
    await render();
    await chooseIdea(QUIET);
    const { heading, items } = asked();
    expect(heading).toBeDefined();
    expect(items).toBeNull();
    expect(text(heading?.nextElementSibling)).toBe("No one has asked to join yet.");

    await chooseIdea(ASKED);
    expect(asked().items).toEqual(["Tanvi Rao, asked 12 Nov 2026", "Kabir Sethi, asked 17 Nov 2026"]);
  });

  it("reads a view without the field (an older worker) as no asks", async () => {
    const [first] = VIEW.picked!;
    await render({ ...VIEW, picked: [{ ...first!, asked_to_join: undefined }] });
    expect(asked().items).toBeNull();
    expect(document.body.textContent).toContain("No one has asked to join yet.");
  });
});
