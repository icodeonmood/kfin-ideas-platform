// @vitest-environment jsdom
/**
 * S-R3, C-PROMPT.voice, C-PROMPT.anatomy/2, L-QUESTIONS.answer, BLD-B276: "Say your answer" in the answer box, with
 * lane C's capture replaced by a fake that the test moves from state to state (no microphone in a unit test). The mic
 * follows the "+" with the Answer board's name; the hook is on the question's own routes; the notice before the
 * first recording shows (DEC-108); the words heard so far show after the answer and the box waits; a finished note's
 * words go after what the box holds and save with the box's autosave; moving on while a note is on its way stops it
 * and follows once its words are in the first question's box; blocked, paused and failed notes say what Share's box
 * says, keep what was heard, and never stop typing. Synthetic people and words only.
 */
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SharerQuestionSetResponse } from "@/lib/contracts";
import type { VoiceCaptureState, VoiceNote } from "@/lib/voice-capture";

const fake = vi.hoisted(() => {
  type S = { status: string; [k: string]: unknown };
  const listeners = new Set<() => void>();
  const f = {
    state: { status: "idle", notice: null } as S,
    calls: [] as { id: string; base: string | undefined }[],
    start: vi.fn(),
    stop: vi.fn(),
    noticeShown: vi.fn(),
    reset: vi.fn(),
    set(s: S) {
      f.state = s;
      listeners.forEach((l) => l());
    },
    subscribe(l: () => void) {
      listeners.add(l);
      return () => listeners.delete(l);
    },
  };
  f.reset.mockImplementation(() => f.set({ status: "idle", notice: null }));
  return f;
});

vi.mock("@/lib/use-voice-capture", async () => {
  const { useSyncExternalStore } = await import("react");
  return {
    useVoiceCapture: (id: string, options?: { base?: string }) => {
      fake.calls.push({ id, base: options?.base });
      const state = useSyncExternalStore(fake.subscribe, () => fake.state);
      return {
        state,
        start: fake.start,
        stop: fake.stop,
        reset: fake.reset,
        noticeShown: fake.noticeShown,
      };
    },
  };
});
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: () => undefined, push: () => undefined }),
}));

const { AnswerView } = await import("@/app/ideas/[id]/answer/answer-view");
const { MIC_BLOCKED, VOICE_LISTENING } = await import("@/lib/voice-capture");
const { VOICE_NOTICE } = await import("@/lib/voice-stream");
const { BANNERS } = await import("@/lib/killswitch-routes");
type SharerSet = NonNullable<SharerQuestionSetResponse>;

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const IDEA = "IDEA-2026-000944";
const Q1 = "5c2f1e0a-7b3d-4e8f-9a1b-2c3d4e5f6a71";
const Q2 = "5c2f1e0a-7b3d-4e8f-9a1b-2c3d4e5f6a72";

function question(id: string, seq: number, text: string) {
  return { id, seq, part: "often", part_name: "How often", text, suggested: false, answer: null };
}

function set(): SharerSet {
  return {
    id: "6b1d2c3e-4f5a-4b6c-8d7e-9f0a1b2c3d4f",
    idea_id: IDEA,
    idea: { id: IDEA, title: "Investors call to ask why a redemption was held" },
    by: null,
    state: "seen",
    time_to_answer: "3d",
    sent_at: new Date(Date.now() - 3_600_000).toISOString(),
    seen_at: new Date().toISOString(),
    due_at: new Date(Date.now() + 3 * 86_400_000).toISOString(),
    answered_at: null,
    extended_times: 0,
    reminded_at: null,
    count: 2,
    answered: 0,
    overdue: false,
    questions: [
      question(Q1, 1, "How many calls a week reach the Vizag branch about R07?"),
      question(Q2, 2, "Which SMS template sends the code?"),
    ],
    countdown: { label: "3 days left to answer", variant: "normal" },
    deadline: "Answer by Thursday 26 November, 6 pm",
    progress: "0 of 2 answered",
    send_label: "Answer at least one question",
  } as SharerSet;
}

function note(text: string): VoiceNote {
  return {
    streamId: "0b7d9d2e-3c1f-4c55-9a51-2f7b0f6f1a10",
    text,
    spans: [],
    textEn: null,
    enLabel: "Typed up in English",
    seconds: 6,
    endedBy: "person",
    hiddenCount: 0,
    translated: false,
    translationFailure: null,
    lang: "en",
    language: "English",
    summary: "",
  };
}

type Put = { url: string; text: string };

/** The answer's saves, answered as the worker answers them. */
function server(): Put[] {
  const puts: Put[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input);
      if ((init.method ?? "GET").toUpperCase() === "PUT") {
        const text = (JSON.parse(String(init.body)) as { text: string }).text;
        puts.push({ url, text });
        return new Response(JSON.stringify({ id: "a-1", text, files: [], sent: false }), { status: 200 });
      }
      return new Response("{}", { status: 404 });
    }),
  );
  return puts;
}

describe("S-R3, C-PROMPT.voice, BLD-B276: Say your answer", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    fake.calls.length = 0;
    fake.start.mockClear();
    fake.stop.mockClear();
    fake.reset.mockClear();
    fake.noticeShown.mockClear();
    fake.state = { status: "idle", notice: null };
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });
  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  const render = () =>
    act(async () => root.render(createElement(AnswerView, { ideaId: IDEA, initial: set() })));
  const box = () => host.querySelector("textarea")!;
  const mic = () => host.querySelector<HTMLButtonElement>(".ans-tools .ans-mic")!;
  const heading = () => host.querySelector("h2")!.textContent ?? "";
  const button = (name: string) =>
    [...host.querySelectorAll("button")].find(
      (b) => (b.getAttribute("aria-label") ?? b.textContent) === name,
    )!;
  const to = (s: VoiceCaptureState) => act(async () => fake.set(s as never));

  async function flush(ms = 0) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ms);
    });
    for (let i = 0; i < 3; i++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
    }
  }

  async function type(words: string) {
    const setValue = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
    await act(async () => {
      setValue.call(box(), words);
      box().dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  it("C-PROMPT.anatomy/2, S-R3, BLD-B276: the mic follows the \"+\" with the board's name, and the hook is on the question's own routes", async () => {
    server();
    await render();
    const tools = [...host.querySelectorAll(".ans-tools > button")];
    expect(tools.map((b) => b.className.split(" ")[0])).toEqual(["attach-btn", "ans-mic"]);
    expect(mic().getAttribute("aria-label")).toBe("Say your answer");
    expect(mic().getAttribute("title")).toBe("Say your answer");
    expect(mic().getAttribute("aria-pressed")).toBe("false");
    expect(mic().type).toBe("button");
    expect(box().placeholder).toBe("Type your answer, or tap the mic and say it");
    expect(fake.calls.at(-1)).toEqual({ id: Q1, base: `/api/questions/${Q1}/answer/voice` });
    await act(async () => mic().click());
    expect(fake.start).toHaveBeenCalledTimes(1);
  });

  it("DEC-108, BLD-B276: the notice before the first recording shows under the box, and the screen says it showed", async () => {
    server();
    fake.state = { status: "idle", notice: VOICE_NOTICE };
    await render();
    expect(host.textContent).toContain(VOICE_NOTICE);
    expect(fake.noticeShown).toHaveBeenCalled();
  });

  it("L-QUESTIONS.answer, BLD-B276: the words so far show after the answer; a finished note's words stay there and save with the autosave", async () => {
    const puts = server();
    await render();
    await type("About 15 calls a week.");
    await flush(700);
    expect(puts.map((p) => p.text)).toEqual(["About 15 calls a week."]);

    await to({ status: "recording", seconds: 3, maxSeconds: 180, text: "Most on Mondays", spans: [] });
    expect(box().value).toBe("About 15 calls a week. Most on Mondays");
    expect(box().readOnly).toBe(true);
    expect(mic().getAttribute("aria-pressed")).toBe("true");
    expect(mic().getAttribute("aria-label")).toBe("Stop, and use what you said");
    expect(host.querySelector(".ans-vline")!.textContent).toBe(VOICE_LISTENING);
    await act(async () => mic().click());
    expect(fake.stop).toHaveBeenCalledTimes(1);

    await to({ status: "done", note: note("Most on Mondays, after the weekend's redemptions.") });
    await flush();
    const both = "About 15 calls a week. Most on Mondays, after the weekend's redemptions.";
    expect(box().value).toBe(both);
    expect(box().readOnly).toBe(false);
    expect(fake.reset).toHaveBeenCalledTimes(1);
    await flush(700);
    expect(puts.at(-1)).toEqual({ url: `/api/questions/${Q1}/answer`, text: both });
    expect(button("Next")).toBeDefined(); // the answer counts, as a typed one does
  });

  it("BLD-B276: moving on while a note is on its way stops it first, and the move follows once its words are in the first box", async () => {
    const puts = server();
    await render();
    expect(heading()).toContain("How many calls a week");
    await to({ status: "recording", seconds: 2, maxSeconds: 180, text: "About fifteen", spans: [] });
    await act(async () => button("Skip for now").click());
    expect(fake.stop).toHaveBeenCalledTimes(1);
    expect(heading()).toContain("How many calls a week"); // still the first question

    await to({ status: "sending", seconds: 2, text: "About fifteen", spans: [] });
    await flush();
    expect(heading()).toContain("How many calls a week");
    await to({ status: "done", note: note("About fifteen a week.") });
    await flush();
    expect(heading()).toContain("Which SMS template");
    expect(fake.calls.at(-1)).toEqual({ id: Q2, base: `/api/questions/${Q2}/answer/voice` });
    await flush(700);
    expect(puts).toEqual([{ url: `/api/questions/${Q1}/answer`, text: "About fifteen a week." }]);
  });

  it("C-PROMPT.voice, BLD-B276: a blocked microphone shows the device's words as an alert, and typing still works", async () => {
    const puts = server();
    await render();
    await to({ status: "blocked", device: "desktop", ...MIC_BLOCKED.desktop });
    const alert = host.querySelector(".ans-blk")!;
    expect(alert.getAttribute("role")).toBe("alert");
    expect(alert.textContent).toContain(MIC_BLOCKED.desktop.title);
    expect(alert.textContent).toContain(MIC_BLOCKED.desktop.body);
    expect(mic().getAttribute("aria-label")).toBe("Microphone blocked");
    expect(box().readOnly).toBe(false);
    await type("The R07 template.");
    await flush(700);
    expect(puts.map((p) => p.text)).toEqual(["The R07 template."]);
  });

  it("C-PROMPT.voice, BLD-B276: a failed note keeps what was heard in the box and says what Share says; a paused one shows its banner", async () => {
    server();
    await render();
    await to({ status: "failed", reason: "voice_paused", text: "About fifteen", spans: [] });
    await flush();
    expect(box().value).toBe("About fifteen");
    const lines = [...host.querySelectorAll('.ans-vlive[role="alert"] p')].map((p) => p.textContent);
    expect(lines).toEqual([BANNERS["capture.voice"]]);
    expect(fake.reset).not.toHaveBeenCalled();

    await to({ status: "failed", reason: "signed_out", text: "", spans: [] });
    const link = host.querySelector<HTMLAnchorElement>('.ans-vlive[role="alert"] a')!;
    expect(link.textContent).toBe("Sign in again to carry on");
    expect(link.getAttribute("href")).toBe(`/sign-in?next=${encodeURIComponent(`/ideas/${IDEA}/answer`)}`);

    await to({
      status: "paused",
      banner: BANNERS["capture.voice"],
      switchName: "capture.voice",
      text: "",
      spans: [],
      note: null,
    });
    const status = [...host.querySelectorAll('.ans-vlive[role="status"] p')].map((p) => p.textContent);
    expect(status).toEqual([BANNERS["capture.voice"]]);
    expect(box().value).toBe("About fifteen"); // nothing heard is lost
  });
});
