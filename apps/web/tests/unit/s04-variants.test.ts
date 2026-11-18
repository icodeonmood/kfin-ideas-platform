// @vitest-environment jsdom
/**
 * P-DECISIONS.experiments on Tell it (S-04, S-04B; BLD-C170 to C175), against a mocked A-API and a stand-in for the
 * voice capture. S1 "Interview": the intro before the first telling; after it, up to three skippable questions in the
 * conversation (the phone's sheet on a phone) with the panel waiting; the place carried from the server; the draft
 * built once; "Move to Review" mid-way builds first. S3 "Voice first": on a phone's empty S-04 listening starts at once
 * once the microphone is allowed, with "Type instead" and "Stop" in the dock; with no permission, or voice off, it
 * starts with typing. Exposures are lane A's, on the server. Synthetic words only.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Draft } from "@/lib/contracts";
import type { ComposeFlags, InterviewPlace } from "@/lib/flags";
import type { VoiceCaptureState } from "@/lib/voice-capture";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: push, refresh: vi.fn() }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
    createElement("a", { href, ...rest }, children as never),
}));

const v = vi.hoisted(() => ({
  state: { status: "idle", notice: null } as VoiceCaptureState,
  listeners: new Set<() => void>(),
  start: null as unknown as () => Promise<void>,
  stop: null as unknown as () => void,
}));
function setVoice(s: VoiceCaptureState) {
  v.state = s;
  for (const l of v.listeners) l();
}
vi.mock("@/lib/use-voice-capture", async () => {
  const React = await import("react");
  return {
    useVoiceCapture: () => {
      const state = React.useSyncExternalStore(
        (l: () => void) => {
          v.listeners.add(l);
          return () => v.listeners.delete(l);
        },
        () => v.state,
        () => v.state,
      );
      return { state, start: v.start, stop: v.stop, reset: () => undefined, noticeShown: () => undefined };
    },
  };
});

const { Compose, noteOutcomes, clock } = await import("@/app/share/compose");

const DRAFT = "6f1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a5b";
const WORDS =
  "Investors who change their bank mandate at the branch wait a week before the new mandate shows. It happens about 25 times a week.";

function draft(over: Partial<Draft> = {}): Draft {
  const now = new Date().toISOString();
  return {
    id: DRAFT,
    owner_id: "u-1",
    channel: "web",
    messages: [
      {
        id: "m-1",
        text: WORDS,
        at: now,
        at_label: "Just now",
        device: "laptop",
        via: "typed",
        files: [],
        spans: [],
      },
    ],
    parts: {
      title: { state: "filled", value: "Bank mandate changes take a week to show" },
      summary: { state: "filled", value: "A new mandate takes a week to show." },
      often: { state: "filled", value: "About 25 times a week at one branch", why: "From your words" },
      who: { state: "filled", value: ["Investors"] },
      value: { state: "filled", value: ["saves_time"] },
      area: { state: "filled", value: "Investor service" },
      similar: { state: "filled", value: [] },
    },
    hidden: [],
    sorting: {} as Draft["sorting"],
    files: [],
    step: "tell",
    saved_at: now,
    saved_on: { device: "laptop", this_device: true },
    saved_labels: null,
    ready: true,
    min_chars: 30,
    char_count: WORDS.length,
    receipt: ["Your draft is ready. Add a detail, or check it."],
    suggestions: [],
    run: { id: "r-0", state: "done" },
    ...over,
  };
}

type Sent = { method: string; url: string; key: string | null; body: Record<string, unknown> };
let sent: Sent[];
let route: (s: Sent) => { status: number; body: unknown } | null;
let phone: boolean;
let micState: PermissionState | "throws";

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: false });
  sent = [];
  phone = false;
  micState = "prompt";
  push.mockClear();
  v.state = { status: "idle", notice: null };
  v.start = vi.fn(async () => setVoice({ status: "asking" }));
  v.stop = vi.fn(() => setVoice({ status: "idle", notice: null }));
  const mem = new Map<string, string>();
  const store = {
    getItem: (k: string) => mem.get(k) ?? null,
    setItem: (k: string, val: string) => void mem.set(k, String(val)),
    removeItem: (k: string) => void mem.delete(k),
    clear: () => mem.clear(),
  };
  vi.stubGlobal("localStorage", store);
  Object.defineProperty(window, "localStorage", { value: store, configurable: true });
  Object.defineProperty(navigator, "onLine", { get: () => true, configurable: true });
  Object.defineProperty(navigator, "permissions", {
    configurable: true,
    value: {
      query: async () => {
        if (micState === "throws") throw new TypeError("no such permission");
        return { state: micState };
      },
    },
  });
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: phone, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  );
  vi.stubGlobal(
    "EventSource",
    class {
      addEventListener() {}
      close() {}
    },
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const s: Sent = {
        method: init.method ?? "GET",
        url: String(input),
        key: new Headers(init.headers).get("Idempotency-Key"),
        body: typeof init.body === "string" ? JSON.parse(init.body) : {},
      };
      sent.push(s);
      const r = route(s) ?? defaultRoute(s);
      return new Response(JSON.stringify(r.body), { status: r.status });
    }),
  );
  route = () => null;
});

function defaultRoute(s: Sent): { status: number; body: unknown } {
  if (s.url.startsWith("/api/flags/")) return { status: 204, body: null };
  if (s.url === "/api/drafts?recent=1") return { status: 200, body: { items: [] } };
  if (s.url.startsWith(`/api/drafts/${DRAFT}`) && s.method === "GET") return { status: 200, body: draft() };
  return { status: 404, body: { error: { code: "not_found", message: "We couldn't find that draft." } } };
}

let host: HTMLDivElement;
let root: Root;

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function mount(props: {
  draftId: string | null;
  flags?: ComposeFlags | null;
  interviewPlace?: InterviewPlace | null;
}) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root.render(createElement(Compose, { firstName: "Kavya", ...props }));
  });
  await settle();
}

async function settle(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

const text = () => host.textContent ?? "";
const button = (name: string) =>
  [...host.querySelectorAll("button, a")].find(
    (b) => (b.getAttribute("aria-label") ?? b.textContent ?? "").trim() === name,
  ) as HTMLButtonElement | undefined;
const posts = (path: string) => sent.filter((s) => s.method === "POST" && s.url === path);
const INTERVIEW = { interview: true, voiceFirst: null } satisfies ComposeFlags;
const STARTED: InterviewPlace = { started: true, done: {}, ended: null };

function typeInto(el: HTMLInputElement | HTMLTextAreaElement, value: string) {
  act(() => {
    const proto = el instanceof HTMLInputElement ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

function interviewRoute(after: (s: Sent) => InterviewPlace, extra: Partial<Record<string, unknown>> = {}) {
  route = (s) =>
    s.method === "POST" && s.url === `/api/drafts/${DRAFT}/interview`
      ? { status: 200, body: { interview: after(s), run_id: null, ...extra } }
      : null;
}

describe("S1 Interview, S-04 before the first telling (Compose.md simulatorS1=Interview)", () => {
  it("S-04 the panel lists the three questions instead of the draft's slots; the browser logs no exposure", async () => {
    await mount({ draftId: null, flags: INTERVIEW });
    expect(text()).toContain("Tell it in your words first. Then three short questions, each one skippable.");
    const items = [...host.querySelectorAll(".ivi li")].map((li) => li.textContent);
    expect(items).toEqual(["How often does it happen?", "Who feels it most?", "Any rough size?"]);
    expect(text()).not.toContain("Your title appears here");
    expect(text()).not.toContain("Waiting for your words");
    // The exposure is lane A's, logged on the server as the page renders (BLD-A216).
    expect(posts("/api/flags/exposure")).toEqual([]);
  });

  it("S-04 without flags from the page: the default, and nothing is logged", async () => {
    await mount({ draftId: null });
    expect(text()).toContain("Your title appears here");
    expect(text()).not.toContain("Tell it in your words first.");
    expect(sent.filter((s) => s.url.startsWith("/api/flags/"))).toEqual([]);
  });
});

describe("S1 Interview, S-04B after the first telling (L-DRAFT.parts/10, V-ACC.share/15)", () => {
  it("starts, asks one at a time with Skip, the panel waits; an answer goes with its own key; built once", async () => {
    let step = 0;
    interviewRoute((s) => {
      step += 1;
      if (s.body.action === "start") return STARTED;
      if (step === 2) return { started: true, done: { often: "skipped" }, ended: null };
      if (step === 3) return { started: true, done: { often: "skipped", who: "answered" }, ended: null };
      return {
        started: true,
        done: { often: "skipped", who: "answered", size: "skipped" },
        ended: "finished",
      };
    });
    await mount({ draftId: DRAFT, flags: INTERVIEW, interviewPlace: null });
    expect(posts(`/api/drafts/${DRAFT}/interview`).map((s) => s.body)).toEqual([{ action: "start" }]);
    expect(text()).toContain("Three quick questions to round it off. Skip any of them.");
    expect(text()).toContain("Question 1 of 3. Skip any of them.");
    expect(host.querySelector(".ivq")!.textContent).toBe("How often does it happen, roughly?");
    expect(host.querySelector(".ivq")!.tagName).toBe("H2");
    expect(button("Use “About 25 times a week at one branch”")).toBeTruthy();
    const answer = host.querySelector(".iv input") as HTMLInputElement;
    expect(answer.labels?.[0]?.textContent).toBe("Your answer");
    expect(answer.placeholder).toBe("For example, about 20 times a week");
    // The panel waits; the receipt waits too
    expect(text()).toContain("Your draft appears here once you've answered or skipped the questions.");
    expect(text()).not.toContain("Bank mandate changes take a week to show");
    expect(text()).not.toContain("Your draft is ready. Add a detail, or check it.");

    await act(async () => {
      button("Skip this one")!.click();
    });
    await settle();
    expect(posts(`/api/drafts/${DRAFT}/interview`)[1]!.body).toEqual({ action: "skip", question: "often" });
    expect(text()).toContain("Question 2 of 3. Skip any of them.");
    expect(host.querySelector(".ivq")!.textContent).toBe("Who feels it most?");
    // Moving on puts focus in the next question's box
    expect(document.activeElement).toBe(host.querySelector(".iv input"));

    typeInto(host.querySelector(".iv input") as HTMLInputElement, "Branch staff and investors");
    await act(async () => {
      button("Next question")!.click();
    });
    await settle();
    const answered = posts(`/api/drafts/${DRAFT}/interview`)[2]!;
    expect(answered.body).toEqual({ action: "answer", question: "who", text: "Branch staff and investors" });
    expect(answered.key).toMatch(/^[0-9a-f-]{36}$/);

    expect(text()).toContain("Question 3 of 3. Skip any of them.");
    expect(host.querySelector(".ivq")!.textContent).toBe("Any rough size? Hours or money, a guess is fine.");
    expect(button("Show my draft")).toBeTruthy();
    // An empty box counts as a skip
    await act(async () => {
      button("Show my draft")!.click();
    });
    await settle(20);
    expect(posts(`/api/drafts/${DRAFT}/interview`)[3]!.body).toEqual({ action: "skip", question: "size" });
    expect(host.querySelector(".iv")).toBeNull();
    expect(text()).toContain("Bank mandate changes take a week to show");
    expect(text()).toContain("Your draft is ready. Add a detail, or check it.");
    expect(document.activeElement).toBe(host.querySelector("textarea"));
  });

  it("Use “…” fills the answer with the draft's own words, for the person to send", async () => {
    interviewRoute(() => STARTED);
    await mount({ draftId: DRAFT, flags: INTERVIEW, interviewPlace: STARTED });
    act(() => button("Use “About 25 times a week at one branch”")!.click());
    expect((host.querySelector(".iv input") as HTMLInputElement).value).toBe(
      "About 25 times a week at one branch",
    );
    expect(button("Use “About 25 times a week at one branch”")).toBeUndefined();
    expect(posts(`/api/drafts/${DRAFT}/interview`)).toEqual([]); // carried on: no second start
  });

  it("nothing is lost on reload: the place from the server carries on at the next question", async () => {
    await mount({
      draftId: DRAFT,
      flags: INTERVIEW,
      interviewPlace: { started: true, done: { often: "answered" }, ended: null },
    });
    expect(text()).toContain("Question 2 of 3. Skip any of them.");
    expect(posts(`/api/drafts/${DRAFT}/interview`)).toEqual([]);
  });

  it("a draft picked up later starts no questions (ComposeResume.md draws the default)", async () => {
    route = (s) =>
      s.method === "GET" && s.url.startsWith(`/api/drafts/${DRAFT}`)
        ? { status: 200, body: draft({ saved_on: { device: "phone", this_device: false } }) }
        : null;
    await mount({ draftId: DRAFT, flags: INTERVIEW, interviewPlace: null });
    expect(posts(`/api/drafts/${DRAFT}/interview`)).toEqual([]);
    expect(host.querySelector(".iv")).toBeNull();
    expect(text()).toContain("Bank mandate changes take a week to show");
  });

  it("Move to Review mid-way builds what was answered first, then goes on to Check it", async () => {
    interviewRoute(() => ({ started: true, done: { often: "answered" }, ended: "left" }), { run_id: "r-2" });
    await mount({
      draftId: DRAFT,
      flags: INTERVIEW,
      interviewPlace: { started: true, done: { often: "answered" }, ended: null },
    });
    const move = button("Move to Review") as unknown as HTMLAnchorElement;
    await act(async () => {
      move.click();
    });
    await settle();
    expect(posts(`/api/drafts/${DRAFT}/interview`).map((s) => s.body)).toEqual([{ action: "finish" }]);
    expect(push).toHaveBeenCalledWith(`/share/${DRAFT}/check`);
  });

  it("the default variant on S-04B: no questions, exactly as before", async () => {
    await mount({ draftId: DRAFT, flags: { interview: false, voiceFirst: null }, interviewPlace: null });
    expect(host.querySelector(".iv")).toBeNull();
    expect(text()).toContain("Your draft is ready. Add a detail, or check it.");
    expect(posts(`/api/drafts/${DRAFT}/interview`)).toEqual([]);
    expect(sent.filter((s) => s.url.startsWith("/api/flags/"))).toEqual([]);
  });
});

describe("S1 Interview on a phone (PhoneCompose.md simulatorS1=Interview)", () => {
  it("the sheet opens on the question; its peek says what comes next; so far, Up to date and Done", async () => {
    phone = true;
    route = (s) =>
      s.method === "GET" && s.url.startsWith(`/api/drafts/${DRAFT}`)
        ? {
            status: 200,
            body: draft({
              hidden: [
                { id: "h1", kind: "folio", masked: "Folio ••••89", state: "hidden" },
                { id: "h2", kind: "pan", masked: "PAN ••••4F", state: "hidden" },
              ] as Draft["hidden"],
            }),
          }
        : null;
    await mount({ draftId: DRAFT, flags: INTERVIEW, interviewPlace: STARTED });
    const peek = host.querySelector(".dpeek")!;
    expect(peek.getAttribute("aria-expanded")).toBe("true");
    expect(peek.textContent).toContain("3 quick questions, then your draft");
    expect(text()).toContain("So far we hid 2 personal details and suggested 3 sortings.");
    expect(host.querySelector(".dsheet .ivq")!.tagName).toBe("H3");
    expect(host.querySelectorAll(".iv")).toHaveLength(1); // in the sheet only, not in the conversation too
    expect(text()).toContain("Up to date");
    act(() => button("Done")!.click());
    expect(peek.getAttribute("aria-expanded")).toBe("false");
    expect(posts("/api/flags/exposure")).toEqual([]);
  });
});

describe("S3 Voice first on a phone's S-04 (PhoneCompose.md simulatorS3=Voice first, state Speaking)", () => {
  const VOICE_FIRST = { interview: false, voiceFirst: "listen" } satisfies ComposeFlags;
  const events = () => posts("/api/flags/events").map((s) => s.body);

  it("listening starts at once once the page is shown and the mic is allowed; Type instead and Stop in the dock", async () => {
    phone = true;
    micState = "granted";
    await mount({ draftId: null, flags: VOICE_FIRST });
    expect(v.start).toHaveBeenCalledTimes(1);
    expect(button("Type instead")).toBeTruthy();
    expect(button("Stop")).toBeTruthy(); // nothing heard yet
    expect(button("Move to Review")).toBeUndefined();
    act(() =>
      setVoice({ status: "recording", seconds: 14, maxSeconds: 180, text: "Investors call us", spans: [] }),
    );
    await settle();
    expect(button("Stop, 0:14")).toBeTruthy();
    expect(events()).toEqual([{ flag: "s3", event: "s3.listen", outcome: "started", screen: "S-04" }]);
    // Said politely for a screen reader (C-PROMPT's status line)
    expect(host.querySelector('[role="status"].vh')?.textContent).toBe("Listening. Up to 3 minutes.");

    await act(async () => {
      button("Type instead")!.click();
      await vi.advanceTimersByTimeAsync(20);
    });
    expect(v.stop).toHaveBeenCalledTimes(1);
    expect(document.activeElement).toBe(host.querySelector("textarea"));
    expect(button("Move to Review")).toBeTruthy();
    expect(events().at(-1)).toEqual({
      flag: "s3",
      event: "s3.listen",
      outcome: "typed_instead",
      screen: "S-04",
    });
  });

  it("no mic permission yet: the phone starts with typing, exactly as the default does", async () => {
    phone = true;
    for (const state of ["prompt", "denied", "throws"] as const) {
      micState = state;
      sent = [];
      await mount({ draftId: null, flags: VOICE_FIRST });
      expect(v.start).not.toHaveBeenCalled();
      expect(button("Type instead")).toBeUndefined();
      expect(events()).toEqual([
        { flag: "s3", event: "s3.listen", outcome: "no_permission", screen: "S-04" },
      ]);
      act(() => root.unmount());
      host.remove();
    }
  });

  it("voice off (kill switches beat the flag): typing first, and nothing asks for the mic", async () => {
    phone = true;
    micState = "granted";
    await mount({ draftId: null, flags: { interview: false, voiceFirst: "voice_off" } });
    expect(v.start).not.toHaveBeenCalled();
    expect(events()).toEqual([{ flag: "s3", event: "s3.listen", outcome: "voice_off", screen: "S-04" }]);
  });

  it("only on a phone's new S-04: not on a desktop, not when an earlier draft is offered, not on S-04B", async () => {
    micState = "granted";
    await mount({ draftId: null, flags: VOICE_FIRST }); // desktop
    expect(v.start).not.toHaveBeenCalled();
    act(() => root.unmount());
    host.remove();

    phone = true;
    route = (s) =>
      s.url === "/api/drafts?recent=1"
        ? {
            status: 200,
            body: {
              items: [
                {
                  id: DRAFT,
                  title: "Bank mandate changes take a week to show",
                  saved_labels: { prompt_day: "Friday", prompt_line: "Last saved on your phone, 8:42 pm." },
                },
              ],
            },
          }
        : null;
    await mount({ draftId: null, flags: VOICE_FIRST });
    expect(v.start).not.toHaveBeenCalled();
    act(() => root.unmount());
    host.remove();

    route = () => null;
    await mount({ draftId: DRAFT, flags: VOICE_FIRST });
    expect(v.start).not.toHaveBeenCalled();
  });
});

describe("S3's second metric: a voice note sent as heard or corrected (BLD-C175)", () => {
  it("compares each held note's words with what was heard", () => {
    const heard = "the SMS only gives a code";
    expect(noteOutcomes(heard, [{ streamId: "s1", text: heard, textEn: null, prefix: null }])).toEqual([
      "as_heard",
    ]);
    expect(
      noteOutcomes(`${heard} and more typed`, [{ streamId: "s1", text: heard, textEn: null, prefix: null }]),
    ).toEqual(["as_heard"]);
    expect(
      noteOutcomes("the SMS only shows a code", [
        { streamId: "s1", text: heard, textEn: null, prefix: null },
      ]),
    ).toEqual(["corrected"]);
    const typed = "Investors call the branch.";
    expect(
      noteOutcomes(`${typed} ${heard}`, [{ streamId: "s2", text: heard, textEn: null, prefix: typed }]),
    ).toEqual(["as_heard"]);
    expect(
      noteOutcomes(`${typed} the SMS gives only a code`, [
        { streamId: "s2", text: heard, textEn: null, prefix: typed },
      ]),
    ).toEqual(["corrected"]);
    expect(clock(14)).toBe("0:14");
    expect(clock(75)).toBe("1:15");
  });
});
