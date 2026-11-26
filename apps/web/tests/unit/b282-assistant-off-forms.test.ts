// @vitest-environment jsdom
/**
 * DEC-143 (f), BLD-B282: while the assistant is off, the Showcase brief (S-ONE's sheet), the Ember note and
 * delivery's three optional notes (the Friday check-in, the completion and a result) still refuse to save. Each says
 * it saves once the assistant is back, and keeps the words as typed in its field. fetch is a stub answering as the
 * web app's routes do (`{ error: "assistant_off" }`, 503); synthetic people and words only.
 */
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SAVES_ONCE_BACK } from "@/lib/assistant-off";
import type { DeliveryDetail } from "@/server/delivery";
import type { ShowcaseBrief } from "@/server/ones";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh, push: vi.fn(), replace: vi.fn() }) }));
vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children?: ReactNode }) =>
    createElement("a", { href }, children),
}));

const { ShowcaseSheet } = await import("@/app/one/showcase-sheet");
const { NoteForm } = await import("@/app/ember/compose/actions");
const { DeliveryView } = await import("@/app/delivery/[id]/delivery-view");

const BRIEF: ShowcaseBrief = {
  tier: 1,
  tier_name: "One",
  tier_colour: "ember",
  one_id: 3,
  number: 12,
  name: "Kavya Menon",
  measures: {} as ShowcaseBrief["measures"],
  updated_at: null,
  parts: [
    { key: "idea", own: "", from_record: null },
    { key: "progress", own: "", from_record: null },
  ],
};

const DELIVERY = {
  id: 12,
  subject_id: "IDEA-2026-000123",
  subject_type: "idea",
  label: "Fewer returned KYC forms",
  track: "fix",
  track_words: "Fix",
  state: "shipped",
  state_words: "Measuring",
  owner: null,
  sponsor: null,
  pm: null,
  pack: { unit: "days", baseline: 10, target: 2, spend: "none" },
  metric: "Days to fix a returned form",
  objective: null,
  missing: [],
  sponsor_approved_at: null,
  phase: null,
  phase_words: null,
  gate_status: null,
  blocked_since: null,
  link_state: "none",
  pipeline_page_id: null,
  completion: null,
  completion_notes: null,
  completed_at: null,
  milestones: [],
  measurements: [
    {
      mark: "day_30",
      due_at: "2026-12-20T10:00:00+05:30",
      results: {},
      notes: null,
      filled_at: null,
      confirmed_at: null,
      finance_confirmed: false,
      can_fill: true,
      can_confirm: false,
      can_finance_confirm: false,
    },
  ],
  evidence: [],
  checkins: {
    recent: [],
    this_week: "2026-11-23",
    replied_this_week: false,
    can_reply: true,
    statuses: [{ id: "on_track", words: "On track" }],
  },
  writeup: null,
  outcome: null,
  shipped_at: null,
  resolved_at: null,
  closed_at: null,
  options: {
    tracks: ["fix"],
    products: [],
    feature_types: [],
    compliance_tiers: [],
    metric_units: ["days"],
    phases: [],
    measure_units: { time: ["hours"], money: ["inr"], effort: ["people"], scale: ["branches"] },
  },
  can: {
    edit: false,
    submit: false,
    approve: false,
    set_phase: false,
    link: false,
    add_milestone: false,
    complete: true,
    approve_completion: false,
    add_evidence: false,
  },
} as unknown as DeliveryDetail;

let host: HTMLElement;
let root: Root;
const saves: Array<{ url: string; method: string }> = [];

beforeEach(() => {
  saves.length = 0;
  refresh.mockClear();
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  const dialog = HTMLDialogElement.prototype as { showModal?: () => void; close?: () => void };
  dialog.showModal = function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  dialog.close = function (this: HTMLDialogElement) {
    this.removeAttribute("open");
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      if (method === "GET") return new Response(JSON.stringify(BRIEF), { status: 200 });
      saves.push({ url, method });
      return new Response(JSON.stringify({ error: "assistant_off" }), { status: 503 });
    }),
  );
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

async function settle() {
  for (let i = 0; i < 5; i++) await act(async () => await Promise.resolve());
}

/** Type into a React-controlled field as a person does. */
function type(el: HTMLTextAreaElement, value: string) {
  const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
  act(() => {
    set?.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function submit(form: HTMLFormElement) {
  await act(async () => {
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  });
  await settle();
}

const formWith = (text: string): HTMLFormElement => {
  const form = [...host.querySelectorAll("form")].find((f) => f.textContent?.includes(text));
  if (!form) throw new Error(`no form with "${text}"`);
  return form;
};

describe("DEC-143 (f), BLD-B282: the assistant off, the words stay", () => {
  it("the Showcase brief says it saves once the assistant is back and keeps every part as typed", async () => {
    act(() => root.render(createElement(ShowcaseSheet, { onClose: () => undefined })));
    await settle();
    const fields = [...host.querySelectorAll("textarea")];
    expect(fields).toHaveLength(2);
    const [idea, progress] = fields as [HTMLTextAreaElement, HTMLTextAreaElement];
    type(idea, "Fewer returned forms at the branch.");
    type(progress, "Two branches use it.");
    await submit(formWith("Save your brief"));
    expect(saves).toEqual([{ url: "/api/me/one/showcase", method: "PUT" }]);
    expect(host.textContent).toContain(SAVES_ONCE_BACK);
    expect(idea.value).toBe("Fewer returned forms at the branch.");
    expect(progress.value).toBe("Two branches use it.");
  });

  it("the Ember note says so and keeps the chair's words", async () => {
    act(() => root.render(createElement(NoteForm, { id: 7, initial: null })));
    const note = host.querySelector("textarea") as HTMLTextAreaElement;
    type(note, "We look for problems people meet every week.");
    await submit(formWith("Save the note"));
    expect(saves).toEqual([{ url: "/api/ember/7/note", method: "PUT" }]);
    expect(host.querySelector('[role="alert"]')?.textContent).toBe(SAVES_ONCE_BACK);
    expect(note.value).toBe("We look for problems people meet every week.");
    expect(refresh).not.toHaveBeenCalled();
  });

  it.each([
    ["the Friday check-in's note", "How is it going this week?", "/api/delivery/12/checkin", "POST"],
    ["the completion's notes", "send the numbers", "/api/delivery/12/complete", "POST"],
    ["a result's notes", "Fill in the results", "/api/delivery/12/measurements/day_30", "PUT"],
  ])("%s says so and keeps the words", async (_name, heading, url, method) => {
    act(() => root.render(createElement(DeliveryView, { d: DELIVERY })));
    const form = formWith(heading);
    const note = form.querySelector("textarea") as HTMLTextAreaElement;
    type(note, "Counted at six branches this week.");
    await submit(form);
    expect(saves).toEqual([{ url, method }]);
    expect(form.querySelector('[role="alert"]')?.textContent ?? host.textContent).toContain(SAVES_ONCE_BACK);
    expect(note.value).toBe("Counted at six branches this week.");
    expect(refresh).not.toHaveBeenCalled();
  });
});
