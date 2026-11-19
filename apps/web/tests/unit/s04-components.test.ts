// @vitest-environment jsdom
/**
 * Tell it's components (S-04, S-04B): C-PROMPT (keys, the round button, speaking, blocked, the notice, the English
 * copy), C-DRAFT-LOADER (the progress bar and its line), C-DRAFT-PANEL (the slots, "Your call", a failed part,
 * the readiness lines, Move to Review) and C-HIDDEN ("Show it" waits for a reason, then shows why, and "Hide it").
 * Copy from reference/copy/Compose.md and ComposeResume.md. Synthetic words only. (BLD-C120, C121, C124, C125)
 */
import { act, createElement, type ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DraftLoader } from "@/components/compose/draft-loader";
import { DraftPanel, READINESS, waitingLine, type PanelProps } from "@/components/compose/draft-panel";
import { HiddenDetails } from "@/components/compose/hidden";
import { labelOnce } from "@/lib/compose/hidden";
import { Prompt, PROMPT_COPY, type PromptProps } from "@/components/compose/prompt";
import type { Draft, IdeaPreview, SimilarMatch } from "@/lib/contracts";
import { fromDraft } from "@/lib/compose/live";
import { MIC_BLOCKED, VOICE_LISTENING, type VoiceCaptureState } from "@/lib/voice-capture";
import { VOICE_EN_LABEL, VOICE_NOTICE } from "@/lib/voice-stream";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
    createElement("a", { href, ...rest }, children as never),
}));

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

function render(el: ReactElement) {
  act(() => root.render(el));
}

const button = (name: string) =>
  [...host.querySelectorAll("button, a")].find(
    (b) => (b.getAttribute("aria-label") ?? b.textContent ?? "").trim() === name,
  ) as HTMLButtonElement | undefined;

// ── C-PROMPT ─────────────────────────────────────────────────────────────────────────────────────────────────

function prompt(
  over: Partial<PromptProps> = {},
  voice: VoiceCaptureState | null = { status: "idle", notice: null },
) {
  const calls = { send: 0, start: 0, stop: 0, shown: 0, mod: 0, changed: [] as string[] };
  const props: PromptProps = {
    value: "",
    onChange: (v) => calls.changed.push(v),
    onSend: () => (calls.send += 1),
    onModEnter: () => (calls.mod += 1),
    sendLabel: "Start my draft",
    label: PROMPT_COPY.firstLabel,
    placeholder: PROMPT_COPY.firstPlaceholder,
    keyHint: true,
    device: "desktop",
    micFirst: true,
    voice: voice
      ? {
          state: voice,
          start: () => (calls.start += 1),
          stop: () => (calls.stop += 1),
          noticeShown: () => (calls.shown += 1),
        }
      : null,
    ...over,
  };
  render(createElement(Prompt, props));
  return calls;
}

describe("C-PROMPT (S-04, S-04B; BLD-C124)", () => {
  it("S-04.empty/1 the empty box: labelled 'Describe the problem', the round button is 'Tap to start speaking'", () => {
    const calls = prompt();
    const box = host.querySelector("textarea")!;
    expect(box.labels?.[0]?.textContent).toBe("Describe the problem");
    expect(box.placeholder).toMatch(/^For example: when a redemption is rejected/);
    expect(button("Tap to start speaking")).toBeTruthy();
    expect(host.textContent).toContain("Not recording until you do");
    act(() => button("Tap to start speaking")!.click());
    expect(calls.start).toBe(1);
    expect(button("Start my draft")).toBeUndefined();
  });

  it("C-PROMPT.keys/1 with words: the key hint, 'Speak instead', and Enter sends while Shift and Enter does not", () => {
    const calls = prompt({ value: "Investors call the branch about R07 codes" });
    expect(host.textContent).toContain("Enter starts your draft. Shift and Enter for a new line.");
    expect(button("Speak instead")?.getAttribute("aria-pressed")).toBe("false");
    const send = button("Start my draft")!;
    expect(send.getAttribute("aria-disabled")).toBeNull();
    const box = host.querySelector("textarea")!;
    act(() => {
      box.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", shiftKey: true, bubbles: true }));
    });
    expect(calls.send).toBe(0);
    act(() => {
      box.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    });
    expect(calls.send).toBe(1);
    act(() => {
      box.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", ctrlKey: true, bubbles: true }));
    });
    expect(calls.mod).toBe(1); // C-PROMPT.keys/2
  });

  it("C-PROMPT.voice listening: the words grow in the box, 'Stop, and use what you said', and it is told once", () => {
    const calls = prompt(
      { value: "" },
      { status: "recording", seconds: 4, maxSeconds: 180, text: "Folio wale customers ko", spans: [] },
    );
    expect(host.querySelector("textarea")!.value).toBe("Folio wale customers ko");
    expect(host.querySelector("textarea")!.readOnly).toBe(true);
    const stop = button("Stop, and use what you said")!;
    expect(stop.getAttribute("aria-pressed")).toBe("true");
    expect(button("Type or speak first")?.getAttribute("aria-disabled")).toBe("true");
    const told = host.querySelector('[role="status"]')!;
    expect(told.textContent).toBe(VOICE_LISTENING); // the state, never the seconds ticking
    expect(told.textContent).not.toContain("0:04"); // never the seconds ticking
    act(() => stop.click());
    expect(calls.stop).toBe(1);
  });

  it("C-PROMPT.voice blocked (desktop): 'Microphone blocked' and the warning under the box as an alert", () => {
    prompt({}, { status: "blocked", device: "desktop", ...MIC_BLOCKED.desktop });
    expect(button("Microphone blocked")).toBeTruthy();
    const alert = host.querySelector('[role="alert"]')!;
    expect(alert.textContent).toContain("Your browser has blocked the microphone.");
    expect(alert.textContent).toContain(
      "Allow it from the lock icon in the address bar, then try again. Or just type in the box above.",
    );
    expect(host.querySelector("textarea")!.readOnly).toBe(false); // typing always works
  });

  it("C-PROMPT.voice the notice shows before the first recording, and the screen says it showed it", () => {
    const calls = prompt({}, { status: "idle", notice: VOICE_NOTICE });
    expect(host.textContent).toContain(VOICE_NOTICE);
    expect(calls.shown).toBe(1);
  });

  it("L-DRAFT.voice/4 the English copy of a note in another language sits under the box, labelled", () => {
    prompt({ value: "Folio wale customers ko code milta hai", english: "Folio customers get a code" });
    expect(host.textContent).toContain(VOICE_EN_LABEL);
    expect(host.textContent).toContain("Folio customers get a code");
  });

  it("C-HIDDEN.where/1 the person's own text is never changed; the detail is underlined behind it", () => {
    prompt({
      value: "One investor, folio 1234567/89, called.",
      spans: [{ start: 20, end: 30, kind: "folio" }],
    });
    expect(host.querySelector("textarea")!.value).toBe("One investor, folio 1234567/89, called.");
    expect(host.querySelector(".mirror .pii")!.textContent).toBe("1234567/89");
  });
});

// ── C-DRAFT-LOADER ───────────────────────────────────────────────────────────────────────────────────────────

describe("C-DRAFT-LOADER (S-04, S-04B; BLD-C120)", () => {
  const run = {
    parts: [
      { key: "similar" as const, mean_ms: 2600 },
      { key: "title" as const, mean_ms: 1800 },
      { key: "value" as const, mean_ms: 1500 },
      { key: "who" as const, mean_ms: 1200 },
      { key: "often" as const, mean_ms: 900 },
      { key: "area" as const, mean_ms: 700 },
    ],
    startedAt: 0,
    answered: { area: 600 },
  };

  it("C-DRAFT-LOADER.a11y a progressbar whose text is the visible line", () => {
    render(createElement(DraftLoader, { run, done: false, now: 600 }));
    expect(host.textContent).toContain("Building your draft");
    expect(host.textContent).toContain("1 of 6 ready, about 2 seconds left");
    const bar = host.querySelector('[role="progressbar"]')!;
    expect(bar.getAttribute("aria-valuetext")).toBe("1 of 6 ready, about 2 seconds left");
    expect(Number(bar.getAttribute("aria-valuenow"))).toBeLessThan(97);
  });

  it("C-DRAFT-LOADER.maths/7 when all six are in: 'All 6 parts are in' and the bar full", () => {
    render(createElement(DraftLoader, { run, done: true, now: 3000 }));
    expect(host.textContent).toContain("All 6 parts are in");
    expect(host.querySelector('[role="progressbar"]')!.getAttribute("aria-valuenow")).toBe("100");
  });
});

// ── C-DRAFT-PANEL ────────────────────────────────────────────────────────────────────────────────────────────

const READY: Draft["parts"] = {
  title: { state: "filled", value: "Distributors can’t see why an SIP registration is stuck" },
  summary: { state: "filled", value: "IRIS shows an SIP registration as Pending with no reason." },
  often: { state: "pinned", value: "About 15 times a week at one branch" },
  who: {
    state: "filled",
    value: ["Distributors", "KFin teams"],
    why: "Suggested because you mentioned distributors and the branch.",
  },
  value: {
    state: "filled",
    value: ["saves_time", "saves_cost"],
    why: "From your words: “about 15 times a week”.",
  },
  area: { state: "failed", value: "" },
  similar: { state: "waiting", value: [] },
};

function panel(over: Partial<PanelProps> = {}, parts: Draft["parts"] | null = READY) {
  const live = fromDraft(
    parts ? ({ parts, hidden: [], ready: true, run: { id: "r", state: "done" } } as unknown as Draft) : null,
  );
  render(
    createElement(DraftPanel, {
      live,
      readiness: "ready",
      moveHref: "/share/d-1/check",
      hidden: null,
      onChangePart: async () => undefined,
      ...over,
    }),
  );
}

describe("C-DRAFT-PANEL (S-04, S-04B; BLD-C125)", () => {
  it("S-04.empty/2 before any words: 'Your draft', 'Forms as you write', the waiting slots, Move to Review disabled", () => {
    panel({ readiness: "more", moveHref: null }, null);
    expect(host.querySelector("h2")!.textContent).toBe("Your draft");
    expect(host.querySelector('[role="status"]')!.textContent).toBe("Forms as you write");
    expect(host.textContent).toContain("Your title appears here");
    expect(host.textContent!.match(/Waiting for your words/g)).toHaveLength(4);
    for (const label of ["How often", "Who it affects", "What it’s worth", "Area"])
      expect(host.textContent).toContain(label);
    expect(host.textContent).toContain("Your draft needs a little more first.");
    expect(button("Move to Review")!.getAttribute("aria-disabled")).toBe("true");
  });

  it("C-DRAFT-PANEL.states filled parts show their why and Change; the person's own reads 'Your call'; a failed one says so", () => {
    panel();
    expect(host.querySelector('[role="status"]')!.textContent).toBe("Up to date");
    expect(host.querySelector("h3")!.textContent).toBe(
      "Distributors can’t see why an SIP registration is stuck",
    );
    expect(host.textContent).toContain("From your first sentence.");
    expect(host.textContent).toContain("Your call"); // How often, changed by the person
    expect(host.textContent).toContain("Saves time, Saves cost");
    expect(host.textContent).toContain("Couldn't work this out. Add it yourself.");
    const changes = [...host.querySelectorAll("button")].filter((b) => b.textContent?.startsWith("Change"));
    expect(changes.map((b) => b.textContent)).toEqual([
      "Change the title",
      "Change How often",
      "Change Who it affects",
      "Change What it’s worth",
      "Change Area",
    ]);
    expect(host.textContent).toContain("Looks right? Check the sorting and send it.");
    const move = button("Move to Review") as unknown as HTMLAnchorElement;
    expect(move.tagName).toBe("A");
    expect(move.getAttribute("href")).toBe("/share/d-1/check");
  });

  it("S-04.rules/2 each disabled state has its line", () => {
    for (const r of ["more", "working", "finishing"] as const) {
      panel({ readiness: r });
      expect(host.textContent).toContain(READINESS[r]);
      expect(button("Move to Review")!.getAttribute("aria-disabled")).toBe("true");
    }
  });

  it("V-FIELDS.tellit/7 Change opens the part in place; an empty value says 'Give it a few words.'", async () => {
    const onChangePart = vi.fn(async () => undefined);
    panel({ onChangePart });
    act(() => button("Change the title")!.click());
    const input = host.querySelector("input[type=text]") as HTMLInputElement;
    expect(input.value).toBe("Distributors can’t see why an SIP registration is stuck");
    act(() => {
      const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
      set.call(input, "");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => button("Done")!.click());
    expect(host.textContent).toContain("Give it a few words.");
    expect(onChangePart).not.toHaveBeenCalled();
    act(() => {
      const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
      set.call(input, "SIP registrations stuck as Pending");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => button("Done")!.click());
    expect(onChangePart).toHaveBeenCalledWith("title", "SIP registrations stuck as Pending");
  });

  it("C-DRAFT-PANEL.behaviour/6 on a phone it is a sheet that peeks with the title, and opens on tap", () => {
    panel({ phone: true });
    const peek = [...host.querySelectorAll("button")].find((b) => b.getAttribute("aria-expanded") !== null)!;
    expect(peek.textContent).toContain("Distributors can’t see why an SIP registration is stuck");
    expect(peek.getAttribute("aria-expanded")).toBe("false");
    act(() => peek.click());
    expect(peek.getAttribute("aria-expanded")).toBe("true");
  });

  it("PhoneCompose.md the empty peek: 'Your draft' and 'Forms here as you write. Tap to see it.'", () => {
    panel({ phone: true, readiness: "more", moveHref: null }, null);
    expect(host.textContent).toContain("Forms here as you write. Tap to see it.");
  });
});

// ── C-HIDDEN ─────────────────────────────────────────────────────────────────────────────────────────────────

describe("C-HIDDEN (S-04, S-04B; BLD-C121)", () => {
  const details = [
    { id: "h-1", kind: "folio" as const, masked: "Folio ••••89", state: "hidden" as const },
    { id: "h-2", kind: "pan" as const, masked: "PAN ••••4F", state: "hidden" as const },
    { id: "h-3", kind: "phone" as const, masked: "Phone ••••10", state: "hidden" as const },
  ];

  it("C-HIDDEN.where one folded bar: 'Personal details hidden', the kinds and the count; it opens to the list", () => {
    render(createElement(HiddenDetails, { details, actions: { show: vi.fn(), hide: vi.fn() } }));
    const bar = host.querySelector("button.hidb")!;
    expect(bar.textContent).toContain("Personal details hidden");
    expect(bar.textContent).toContain("Folio number, PAN and phone number");
    expect(bar.textContent).toContain("3");
    expect(bar.getAttribute("aria-expanded")).toBe("false");
    act(() => (bar as HTMLButtonElement).click());
    expect(host.textContent).toContain("Folio ••••89");
    expect(host.textContent).toContain("Hidden from everyone but you");
    expect(host.textContent).not.toContain("1234567"); // only the masked form
  });

  it("V-ACC.share/8 Show it stays disabled until a reason is picked, then shows why; Hide it reverses", async () => {
    const show = vi.fn(async () => undefined);
    const hide = vi.fn(async () => undefined);
    render(createElement(HiddenDetails, { details: [details[1]!], actions: { show, hide } }));
    act(() => (host.querySelector("button.hidb") as HTMLButtonElement).click());
    act(() => button("Show it")!.click());
    expect(host.textContent).toContain("Only show it if it isn't about a real customer. What is it?");
    expect(host.textContent).toContain("We note your reason with the idea.");
    const confirm = [...host.querySelectorAll("button")].filter((b) => b.textContent === "Show it").at(-1)!;
    expect(confirm.getAttribute("aria-disabled")).toBe("true");
    await act(async () => confirm.click());
    expect(show).not.toHaveBeenCalled();
    const radio = host.querySelector('input[value="internal_reference"]') as HTMLInputElement;
    act(() => radio.click());
    expect(confirm.getAttribute("aria-disabled")).toBeNull();
    await act(async () => confirm.click());
    expect(show).toHaveBeenCalledWith("h-2", "internal_reference");

    render(
      createElement(HiddenDetails, {
        details: [{ ...details[1]!, state: "shown", reason: "internal_reference" }],
        actions: { show, hide },
      }),
    );
    expect(host.textContent).toContain("Shown, because it's an internal reference.");
    await act(async () => button("Hide it")!.click());
    expect(hide).toHaveBeenCalledWith("h-2");
  });
});

// ── similar ideas: C-PREVIEW, then lane F's team-up sheet (BLD-C129) ─────────────────────────────────────────

const RAVI: IdeaPreview = {
  id: "IDEA-2026-001412",
  title: "Rejection SMS codes confuse investors",
  status: "with_review_desk",
  area: "Investor service",
  city: "Hyderabad",
  shared_at: "2026-11-02T10:30:00+05:30",
  lead: { id: "p-ravi", name: "Ravi Nair", first_name: "Ravi", initials: "RN" },
  crew_faces: [{ id: "p-ravi", name: "Ravi Nair", first_name: "Ravi", initials: "RN" }],
  crew_count: 4,
  in_their_words: "Investors get a code, not a reason, and then they call us.",
  looking_for: "Someone who takes these calls at a branch every day.",
  hue: 1,
} as IdeaPreview;
const MATCH = {
  idea: RAVI,
  strength: "close",
  reason: "Close match: the same R07 SMS and the same calls",
} as SimilarMatch;

describe("S-04B similar ideas: Preview, then Team up through lane F's sheet (J-SIMILAR/3; BLD-C129)", () => {
  it("C-PREVIEW opens from the strip, and its Team up opens the sheet for that idea", async () => {
    const open = vi.fn();
    panel({ teamUp: { open, waiting: {} } }, { ...READY, similar: { state: "filled", value: [MATCH] } });
    const strip = host.querySelector("button.simb") as HTMLButtonElement;
    expect(strip.textContent).toContain("1 similar idea");
    expect(strip.textContent).toContain("Colleagues raised something close");
    act(() => strip.click());
    await act(async () => button("Preview: Rejection SMS codes confuse investors")?.click());
    const dialog = document.querySelector('[role="dialog"]')!;
    expect(dialog.textContent).toContain("Close match: the same R07 SMS and the same calls");
    const teamUp = [...dialog.querySelectorAll("button")].find((b) => b.textContent?.trim() === "Team up")!;
    await act(async () => teamUp.click());
    expect(open).toHaveBeenCalledWith("IDEA-2026-001412");
  });

  it("C-SHEET-TEAMUP.after once sent: the sheet's line, or 'Waiting for Ravi'; nothing before", () => {
    expect(waitingLine(MATCH, {})).toBeUndefined();
    expect(waitingLine(MATCH, { "IDEA-2026-001412": "" })).toBe("Waiting for Ravi");
    expect(waitingLine(MATCH, { "IDEA-2026-001412": "Waiting for Ravi Nair" })).toBe("Waiting for Ravi Nair");
  });
});

// ── Lane G's 09:30 walk: a masked detail's label said once in a quote (BLD-C193) ──────────────────────────────

describe("C-DRAFT-PANEL C-HIDDEN L-HIDE BLD-C193: a quote says a masked detail's label once (J-RECOVER/3, /6)", () => {
  /** A synthetic value that is never anywhere on the page: only its masked form is. */
  const RAW = "8800123417";

  it("labelOnce: the label typed just before its masked form goes; any other word stays; the masked form is kept", () => {
    expect(labelOnce("one investor with folio Folio ••••17")).toBe("one investor with Folio ••••17");
    expect(labelOnce("PAN PAN ••••8Z and pan: PAN ••••4F")).toBe("PAN ••••8Z and PAN ••••4F");
    expect(labelOnce("call phone - Phone ••••10 twice")).toBe("call Phone ••••10 twice");
    expect(labelOnce("one investor with Folio ••••17")).toBe("one investor with Folio ••••17");
    expect(labelOnce("the number Folio ••••17")).toBe("the number Folio ••••17");
    expect(labelOnce("portfolio Folio ••••17")).toBe("portfolio Folio ••••17");
    expect(labelOnce("folio Phone ••••10")).toBe("folio Phone ••••10");
    expect(labelOnce("our folio count is high")).toBe("our folio count is high");
  });

  it("the worth quote reads 'with Folio ••••17' once, and no raw value reaches the page", () => {
    panel(
      {},
      {
        ...READY,
        value: {
          state: "filled",
          value: ["saves_time"],
          why: "From your words: “about 2 hours a week for one investor with folio Folio ••••17”",
        },
      },
    );
    const whys = [...host.querySelectorAll(".why")].map((w) => w.textContent);
    expect(whys).toContain("From your words: “about 2 hours a week for one investor with Folio ••••17”");
    expect(host.textContent).not.toMatch(/folio Folio/i);
    expect(host.textContent).toContain("••••17");
    expect(host.innerHTML).not.toContain(RAW);
    expect(host.innerHTML).not.toContain(RAW.slice(0, -2));
  });

  it("a different word before the masked form keeps the label as it was", () => {
    panel(
      {},
      {
        ...READY,
        value: {
          state: "filled",
          value: ["saves_time"],
          why: "From your words: “about 2 hours a week for the investor at Folio ••••17”",
        },
      },
    );
    const whys = [...host.querySelectorAll(".why")].map((w) => w.textContent);
    expect(whys).toContain("From your words: “about 2 hours a week for the investor at Folio ••••17”");
  });
});
