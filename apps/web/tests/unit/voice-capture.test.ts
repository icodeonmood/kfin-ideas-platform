// @vitest-environment jsdom
/**
 * L-DRAFT.voice and C-PROMPT.voice in the browser (BLD-C118, BLD-C119): the capture's states against a mocked
 * microphone, audio graph and fetch. Permission denied leads to blocked with the pack's copy word for word; chunks
 * go in order and a failed one is retried before the next; the 180-second cap ends the note; a kill-switch answer
 * leads to paused with the route table's banner; a dropped connection or an interruption leads to polling until
 * the worker has finished the note; the notice shows before the first recording. Synthetic words only.
 */
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BANNERS } from "@/lib/killswitch-routes";
import { useVoiceCapture } from "@/lib/use-voice-capture";
import {
  MIC_BLOCKED,
  retryAfterMs,
  VOICE_NOTICE_KEY,
  VoiceCapture,
  type VoiceCaptureOptions,
  type VoiceCaptureState,
} from "@/lib/voice-capture";
import { VOICE_EN_LABEL, VOICE_NOTICE } from "@/lib/voice-stream";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const DRAFT = "6f1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a5b";
const STREAM = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d";

// ── the audio graph ──────────────────────────────────────────────────────────────────────────────────────────

class FakeTrack {
  stopped = false;
  private ended: (() => void)[] = [];
  stop() {
    this.stopped = true;
  }
  addEventListener(type: string, fn: () => void) {
    if (type === "ended") this.ended.push(fn);
  }
  end() {
    for (const fn of this.ended) fn();
  }
}

class FakeStream {
  track = new FakeTrack();
  getTracks() {
    return [this.track];
  }
  getAudioTracks() {
    return [this.track];
  }
}

let nodes: FakeNode[] = [];
let contexts: FakeContext[] = [];

class FakeNode {
  port: { onmessage: ((e: { data: unknown }) => void) | null } = { onmessage: null };
  connect = vi.fn();
  disconnect = vi.fn();
  constructor(
    readonly ctx: FakeContext,
    readonly name: string,
  ) {
    nodes.push(this);
  }
}

class FakeContext {
  sampleRate = 48_000;
  state = "suspended";
  destination = {};
  audioWorklet = { addModule: vi.fn(async () => undefined) };
  source = { connect: vi.fn(), disconnect: vi.fn() };
  private listeners: (() => void)[] = [];
  constructor() {
    contexts.push(this);
  }
  createMediaStreamSource = vi.fn(() => this.source);
  resume = vi.fn(async () => {
    this.state = "running";
  });
  close = vi.fn(async () => {
    this.state = "closed";
  });
  addEventListener(type: string, fn: () => void) {
    if (type === "statechange") this.listeners.push(fn);
  }
  becomes(state: string) {
    this.state = state;
    for (const fn of this.listeners) fn();
  }
}

let stream: FakeStream;
let getUserMedia: ReturnType<typeof vi.fn>;

/** `seconds` of sound at 48 kHz, sent the way the worklet sends it (one block a second here, for speed). */
function speak(seconds: number) {
  const node = nodes.at(-1)!;
  for (let s = 0; s < seconds; s++) node.port.onmessage?.({ data: new Float32Array(48_000).fill(0.1) });
}

// ── the server ───────────────────────────────────────────────────────────────────────────────────────────────

type Call = { method: string; path: string; seq?: number; stream?: string; bytes?: number; body?: unknown };
type Reply = { status: number; body: unknown } | "network";

let calls: Call[];
let route: (call: Call) => Reply;

const live = (seq: number, text = "", spans: unknown[] = []) => ({
  status: 200,
  body: { id: STREAM, state: "live", next_seq: seq + 1, seconds: seq + 1, text, spans },
});
const DONE = {
  id: STREAM,
  state: "done",
  seconds: 12,
  ended_by: "person",
  text: "Folio wale customers ko SMS mein code milta hai, reason nahi",
  spans: [{ start: 0, end: 5, kind: "folio" }],
  hidden_count: 1,
  text_en: "Folio customers get a code in the SMS, not a reason",
  text_en_label: VOICE_EN_LABEL,
  translated: true,
  translation_failure: null,
  lang: "hi-IN",
  language: "Hindi",
  summary: "Voice message, 12 seconds, in Hindi",
};

const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
  const url = new URL(input, "http://localhost");
  const call: Call = { method: init?.method ?? "GET", path: url.pathname };
  if (url.searchParams.has("seq")) {
    call.seq = Number(url.searchParams.get("seq"));
    call.stream = url.searchParams.get("stream") ?? "";
    call.bytes = (init?.body as Uint8Array).byteLength;
  } else if (typeof init?.body === "string") {
    call.body = JSON.parse(init.body);
  }
  calls.push(call);
  const reply = route(call);
  if (reply === "network") throw new TypeError("Failed to fetch");
  return {
    ok: reply.status >= 200 && reply.status < 300,
    status: reply.status,
    json: async () => reply.body,
  } as Response;
});

function defaultRoute(call: Call): Reply {
  if (call.path.endsWith("/voice/start")) return { status: 201, body: { id: STREAM, state: "live" } };
  if (call.path.endsWith("/voice/chunk")) return live(call.seq!, "Folio wale customers");
  if (call.path.endsWith("/voice/end")) return { status: 200, body: DONE };
  if (call.path.endsWith(`/voice/${STREAM}`)) return { status: 200, body: DONE };
  return { status: 404, body: { error: "not_found" } };
}

const chunks = () => calls.filter((c) => c.path.endsWith("/voice/chunk"));
const ends = () => calls.filter((c) => c.path.endsWith("/voice/end"));
const polls = () => calls.filter((c) => c.method === "GET");

function memoryStorage() {
  const m = new Map<string, string>();
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v), m };
}

function make(options: VoiceCaptureOptions = {}) {
  const capture = new VoiceCapture(DRAFT, {
    fetch: fetchMock as unknown as typeof fetch,
    storage: memoryStorage(),
    device: "desktop",
    ...options,
  });
  const seen: VoiceCaptureState["status"][] = [capture.getState().status];
  capture.subscribe(() => {
    const s = capture.getState().status;
    if (seen.at(-1) !== s) seen.push(s);
  });
  return { capture, seen };
}

const settle = () => vi.advanceTimersByTimeAsync(0);

beforeEach(() => {
  vi.useFakeTimers();
  nodes = [];
  contexts = [];
  calls = [];
  route = defaultRoute;
  fetchMock.mockClear();
  stream = new FakeStream();
  getUserMedia = vi.fn(async () => stream);
  vi.stubGlobal("AudioContext", FakeContext);
  vi.stubGlobal("AudioWorkletNode", FakeNode);
  Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia }, configurable: true });
  URL.createObjectURL = vi.fn(() => "blob:voice-worklet");
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function recording(options: VoiceCaptureOptions = {}) {
  const made = make(options);
  await made.capture.start();
  await settle();
  expect(made.capture.getState().status).toBe("recording");
  return made;
}

// ── tests ────────────────────────────────────────────────────────────────────────────────────────────────────

describe("C-PROMPT.voice states (BLD-C118, BLD-C119)", () => {
  it("C-PROMPT.voice idle: VOICE_NOTICE shows before the first recording on this device, and not after", async () => {
    const storage = memoryStorage();
    const { capture } = make({ storage });
    expect(capture.getState()).toEqual({ status: "idle", notice: VOICE_NOTICE });
    capture.noticeShown(); // the screen showed it (BLD-C127)
    await capture.start();
    await settle();
    expect(storage.m.get(VOICE_NOTICE_KEY)).toBe("1");
    capture.stop();
    await settle();
    capture.reset();
    expect(capture.getState()).toEqual({ status: "idle", notice: null });
  });

  it("C-PROMPT.voice idle: with storage blocked, the notice shows every time", () => {
    const blocked = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    expect(make({ storage: blocked }).capture.getState()).toEqual({ status: "idle", notice: VOICE_NOTICE });
  });

  it("L-DRAFT.voice/5 permission denied leads to blocked, with C-PROMPT.voice's desktop copy word for word", async () => {
    getUserMedia.mockRejectedValueOnce(Object.assign(new Error("denied"), { name: "NotAllowedError" }));
    const { capture, seen } = make();
    await capture.start();
    await settle();
    expect(seen).toEqual(["idle", "asking", "blocked"]);
    expect(capture.getState()).toEqual({
      status: "blocked",
      device: "desktop",
      title: "Your browser has blocked the microphone.",
      body: "Allow it from the lock icon in the address bar, then try again. Or just type in the box above.",
    });
    expect(calls).toEqual([]); // no stream was opened
    expect(contexts[0]!.close).toHaveBeenCalled();
  });

  it("L-DRAFT.voice/5 on a phone, blocked carries the phone's line (PhoneCompose.md, State: Mic blocked)", async () => {
    getUserMedia.mockRejectedValueOnce(Object.assign(new Error("denied"), { name: "NotAllowedError" }));
    const { capture } = make({ device: "phone" });
    await capture.start();
    await settle();
    expect(capture.getState()).toMatchObject({
      status: "blocked",
      title: "The microphone is off for this app.",
      body: "Turn it on in your phone’s settings, or type above. Your words save as you go.",
    });
    expect(MIC_BLOCKED.phone.body).toContain("phone’s"); // the pack's curly apostrophe
  });

  it("L-DRAFT.voice no microphone, or no AudioWorklet, is failed with a code (typing still works)", async () => {
    getUserMedia.mockRejectedValueOnce(Object.assign(new Error("none"), { name: "NotFoundError" }));
    const a = make().capture;
    await a.start();
    await settle();
    expect(a.getState()).toMatchObject({ status: "failed", reason: "no_microphone" });

    vi.stubGlobal("AudioWorkletNode", undefined);
    const b = make().capture;
    await b.start();
    expect(b.getState()).toMatchObject({ status: "failed", reason: "not_supported" });
  });
});

describe("L-DRAFT.voice upload (BLD-C112, BLD-C118)", () => {
  it("L-DRAFT.voice/2 start, then one-second chunks in order from seq 0 with the stream id, words as they come", async () => {
    let n = 0;
    route = (call) =>
      call.path.endsWith("/voice/chunk")
        ? live(call.seq!, ["Folio", "Folio wale", "Folio wale customers"][n++] ?? "", [
            { start: 0, end: 5, kind: "folio" },
          ])
        : defaultRoute(call);
    const { capture, seen } = await recording();
    expect(seen).toEqual(["idle", "asking", "recording"]);
    expect(calls[0]).toMatchObject({ method: "POST", path: `/api/drafts/${DRAFT}/voice/start` });
    expect(contexts[0]!.audioWorklet.addModule).toHaveBeenCalledWith("blob:voice-worklet");
    expect(nodes[0]!.connect).toHaveBeenCalledWith(contexts[0]!.destination);

    speak(3);
    await settle();
    expect(chunks().map((c) => [c.seq, c.stream, c.bytes])).toEqual([
      [0, STREAM, 32_000],
      [1, STREAM, 32_000],
      [2, STREAM, 32_000],
    ]);
    expect(capture.getState()).toEqual({
      status: "recording",
      seconds: 3,
      maxSeconds: 180,
      text: "Folio wale customers",
      spans: [{ start: 0, end: 5, kind: "folio" }],
    });
  });

  it("L-DRAFT.voice a failed chunk is retried with the same seq, and the next waits for it", async () => {
    let failures = 2;
    route = (call) => {
      if (call.path.endsWith("/voice/chunk") && call.seq === 1 && failures > 0) {
        failures -= 1;
        return failures === 1 ? "network" : { status: 502, body: { error: "voice_unavailable" } };
      }
      return defaultRoute(call);
    };
    const { capture } = await recording();
    speak(3);
    await settle();
    expect(chunks().map((c) => c.seq)).toEqual([0, 1]); // seq 1 failed; seq 2 has not gone
    await vi.advanceTimersByTimeAsync(500);
    expect(chunks().map((c) => c.seq)).toEqual([0, 1, 1]);
    await vi.advanceTimersByTimeAsync(1500);
    expect(chunks().map((c) => c.seq)).toEqual([0, 1, 1, 1, 2]);
    expect(capture.getState().status).toBe("recording");
  });

  it("L-DRAFT.voice/2 stop sends the last part second, ends the note and shows their words and the English copy", async () => {
    const { capture, seen } = await recording();
    speak(2);
    nodes[0]!.port.onmessage?.({ data: new Float32Array(24_000).fill(0.1) }); // half a second more
    await settle();
    capture.stop();
    expect(stream.track.stopped).toBe(true); // the mic is off at once
    await settle();
    expect(chunks().map((c) => [c.seq, c.bytes])).toEqual([
      [0, 32_000],
      [1, 32_000],
      [2, 16_000],
    ]);
    expect(ends()).toEqual([
      { method: "POST", path: `/api/drafts/${DRAFT}/voice/end`, body: { stream: STREAM } },
    ]);
    expect(seen).toEqual(["idle", "asking", "recording", "sending", "done"]);
    const state = capture.getState();
    if (state.status !== "done") throw new Error("not done");
    expect(state.note).toMatchObject({
      streamId: STREAM,
      text: DONE.text,
      textEn: DONE.text_en,
      enLabel: "Typed up in English",
      spans: DONE.spans,
      endedBy: "person",
      summary: "Voice message, 12 seconds, in Hindi",
    });
  });

  it("L-DRAFT.voice/1 the 180-second cap ends the note: 180 chunks, nothing past it, the mic off", async () => {
    const { capture } = await recording();
    speak(185);
    await settle();
    const sent = chunks();
    expect(sent.length).toBe(180);
    expect(sent.at(-1)?.seq).toBe(179);
    expect(sent.reduce((t, c) => t + c.bytes!, 0)).toBe(180 * 32_000);
    expect(stream.track.stopped).toBe(true);
    expect(ends().length).toBe(1);
    expect(capture.getState().status).toBe("done");
  });

  it("L-DRAFT.voice/1 when the worker ends the note at the cap, its answer is the note and no end is sent", async () => {
    route = (call) =>
      call.path.endsWith("/voice/chunk") && call.seq === 179
        ? { status: 200, body: { ...DONE, ended_by: "limit", seconds: 180 } }
        : defaultRoute(call);
    const { capture } = await recording();
    speak(180);
    await settle();
    expect(ends()).toEqual([]);
    expect(capture.getState()).toMatchObject({ status: "done", note: { endedBy: "limit", seconds: 180 } });
  });
});

describe("L-DRAFT.voice paused and lost (BLD-C112, BLD-C119)", () => {
  it("L-DRAFT.voice a kill-switch answer leads to paused with the route table's banner; the kept words fill in", async () => {
    route = (call) =>
      call.path.endsWith("/voice/chunk") && call.seq === 1
        ? {
            status: 503,
            body: { error: "paused", switch: "speech.hosted", banner: BANNERS["speech.hosted"] },
          }
        : defaultRoute(call);
    const { capture } = await recording();
    speak(2);
    await settle();
    expect(capture.getState()).toEqual({
      status: "paused",
      banner: "Voice notes are paused for a short while. You can type instead.",
      switchName: "speech.hosted",
      text: "Folio wale customers",
      spans: [],
      note: null,
    });
    expect(chunks().length).toBe(2); // a paused answer is not retried
    expect(stream.track.stopped).toBe(true);
    expect(ends()).toEqual([]); // ending is paused too; reading it back is not
    await vi.advanceTimersByTimeAsync(2000);
    expect(polls().map((c) => c.path)).toEqual([`/api/drafts/${DRAFT}/voice/${STREAM}`]);
    expect(capture.getState()).toMatchObject({ status: "paused", note: { text: DONE.text } });
  });

  it("L-DRAFT.voice capture.voice off at start: paused with that switch's banner, the mic released", async () => {
    route = (call) =>
      call.path.endsWith("/voice/start")
        ? {
            status: 503,
            body: { error: "paused", switch: "capture.voice", banner: BANNERS["capture.voice"] },
          }
        : defaultRoute(call);
    const { capture } = make();
    await capture.start();
    await settle();
    expect(capture.getState()).toMatchObject({
      status: "paused",
      banner: "Voice notes are coming soon.",
      switchName: "capture.voice",
      note: null,
    });
    expect(stream.track.stopped).toBe(true);
    expect(chunks()).toEqual([]);
  });

  it("L-DRAFT.voice the worker's own pause (speech.hosted read fresh) uses speech.hosted's banner and keeps the words", async () => {
    route = (call) =>
      call.path.endsWith("/voice/chunk")
        ? { status: 503, body: { error: "voice_paused", details: { ...DONE, ended_by: "paused" } } }
        : defaultRoute(call);
    const { capture } = await recording();
    speak(1);
    await settle();
    expect(capture.getState()).toMatchObject({
      status: "paused",
      banner: BANNERS["speech.hosted"],
      switchName: "speech.hosted",
      note: { text: DONE.text, endedBy: "paused" },
    });
    expect(polls()).toEqual([]);
  });

  it("L-DRAFT.voice a dropped connection: after the retries the mic goes off and GET polls until the note is done", async () => {
    let online = false;
    let polled = 0;
    route = (call) => {
      if (!online && call.path.endsWith("/voice/chunk") && call.seq! >= 1) return "network";
      if (call.method === "GET") {
        polled += 1;
        if (!online) return "network";
        return polled < 4
          ? live(1, "Folio wale customers ko")
          : { status: 200, body: { ...DONE, ended_by: "idle" } };
      }
      return defaultRoute(call);
    };
    const { capture, seen } = await recording();
    speak(2);
    await settle();
    await vi.advanceTimersByTimeAsync(500 + 1500 + 3000);
    expect(chunks().map((c) => c.seq)).toEqual([0, 1, 1, 1, 1]);
    expect(stream.track.stopped).toBe(true);
    expect(capture.getState().status).toBe("sending");
    await vi.advanceTimersByTimeAsync(4000); // two polls while offline
    expect(capture.getState().status).toBe("sending");
    online = true;
    await vi.advanceTimersByTimeAsync(2000);
    expect(capture.getState()).toMatchObject({ status: "sending", text: "Folio wale customers ko" });
    await vi.advanceTimersByTimeAsync(2000);
    expect(capture.getState()).toMatchObject({ status: "done", note: { endedBy: "idle", text: DONE.text } });
    expect(seen).toEqual(["idle", "asking", "recording", "sending", "done"]);
    const n = polls().length;
    await vi.advanceTimersByTimeAsync(10_000);
    expect(polls().length).toBe(n); // polling stops once the note is done
  });

  it("L-DRAFT.voice an interruption (the mic taken, the phone locked) ends the note once, then polls if that fails", async () => {
    route = (call) => (call.path.endsWith("/voice/end") ? "network" : defaultRoute(call));
    const { capture } = await recording();
    speak(1);
    await settle();
    contexts[0]!.becomes("interrupted");
    await settle();
    expect(ends().length).toBe(1); // one try, no retries
    expect(capture.getState().status).toBe("sending");
    await vi.advanceTimersByTimeAsync(2000);
    expect(capture.getState()).toMatchObject({ status: "done", note: { text: DONE.text } });
  });

  it("L-DRAFT.voice a track that ends mid-note is an interruption too", async () => {
    const { capture } = await recording();
    speak(1);
    await settle();
    stream.track.end();
    await settle();
    expect(ends().length).toBe(1);
    expect(capture.getState().status).toBe("done");
  });

  it("L-DRAFT.voice polling gives up after its window with stream_lost; a lost stream (410) fails at once", async () => {
    route = (call) =>
      call.path.endsWith("/voice/chunk") ? "network" : call.method === "GET" ? "network" : defaultRoute(call);
    const { capture } = await recording({ pollForMs: 10_000, retryDelaysMs: [] });
    speak(1);
    await settle();
    expect(capture.getState().status).toBe("sending");
    await vi.advanceTimersByTimeAsync(12_000);
    expect(capture.getState()).toMatchObject({ status: "failed", reason: "stream_lost" });

    route = (call) =>
      call.path.endsWith("/voice/chunk")
        ? { status: 410, body: { error: "stream_lost" } }
        : defaultRoute(call);
    const again = await recording();
    speak(1);
    await settle();
    expect(again.capture.getState()).toMatchObject({ status: "failed", reason: "stream_lost" });
  });

  it("L-DRAFT.voice the worker's refusal at start is failed with its code; signed out is signed_out", async () => {
    route = (call) =>
      call.path.endsWith("/voice/start")
        ? { status: 429, body: { error: "too_many_this_hour" } }
        : defaultRoute(call);
    const a = make().capture;
    await a.start();
    await settle();
    expect(a.getState()).toMatchObject({ status: "failed", reason: "too_many_this_hour" });
    expect(stream.track.stopped).toBe(true);

    route = (call) => (call.path.endsWith("/voice/chunk") ? { status: 401, body: {} } : defaultRoute(call));
    stream = new FakeStream();
    const b = await recording();
    speak(1);
    await settle();
    expect(b.capture.getState()).toMatchObject({ status: "failed", reason: "signed_out" });
  });

  it("L-DRAFT.voice leaving the screen ends a live note with keepalive and stops the mic (J-RESUME/1)", async () => {
    const { capture } = await recording();
    speak(1);
    await settle();
    capture.dispose();
    await settle();
    expect(stream.track.stopped).toBe(true);
    const last = fetchMock.mock.calls.at(-1)!;
    expect(last[0]).toBe(`/api/drafts/${DRAFT}/voice/end`);
    expect(last[1]).toMatchObject({ method: "POST", keepalive: true });
    expect(capture.getState().status).toBe("idle");
  });
});

describe("C-PROMPT.voice useVoiceCapture (BLD-C118)", () => {
  it("C-PROMPT.voice the hook re-renders on each state and releases the mic on unmount", async () => {
    const states: string[] = [];
    let api: ReturnType<typeof useVoiceCapture> | null = null;
    function Probe() {
      api = useVoiceCapture(DRAFT, {
        fetch: fetchMock as unknown as typeof fetch,
        storage: memoryStorage(),
        device: "desktop",
      });
      states.push(api.state.status);
      return null;
    }
    const host = document.createElement("div");
    const root = createRoot(host);
    await act(async () => root.render(createElement(Probe)));
    expect(api!.state).toEqual({ status: "idle", notice: VOICE_NOTICE });
    await act(async () => {
      await api!.start();
      await settle();
    });
    expect(api!.state.status).toBe("recording");
    await act(async () => root.unmount());
    expect(stream.track.stopped).toBe(true);
    expect(states).toContain("asking");
  });
});

// ── review fixes (BLD-C127) ──────────────────────────────────────────────────────────────────────────────────

describe("C-PROMPT.voice review fixes (BLD-C127)", () => {
  it("C-PROMPT.voice the notice is marked seen only once the screen has shown it", async () => {
    const storage = memoryStorage();
    const { capture } = make({ storage });
    await capture.start();
    await settle();
    expect(capture.getState().status).toBe("recording");
    expect(storage.m.has(VOICE_NOTICE_KEY)).toBe(false);
  });

  it("C-PROMPT.voice iOS: the context is made and resumed inside the tap, before anything is awaited", () => {
    const { capture } = make();
    void capture.start(); // not awaited: what happened synchronously is what the gesture covers
    expect(contexts).toHaveLength(1);
    expect(contexts[0]!.resume).toHaveBeenCalledTimes(1);
    expect(getUserMedia).toHaveBeenCalledTimes(1);
    expect(contexts[0]!.resume.mock.invocationCallOrder[0]!).toBeLessThan(
      getUserMedia.mock.invocationCallOrder[0]!,
    );
  });

  it("C-PROMPT.voice iOS: recording is set before the resume settles, and a hung resume ends the note after 5 s", async () => {
    let resolveResume: (() => void) | null = null;
    class SlowContext extends FakeContext {
      resume = vi.fn(() => new Promise<void>((r) => (resolveResume = r)));
    }
    vi.stubGlobal("AudioContext", SlowContext);
    const { capture } = make({ resumeTimeoutMs: 5_000 });
    void capture.start();
    await settle();
    expect(capture.getState().status).toBe("recording"); // no audio dropped while the resume is pending
    await vi.advanceTimersByTimeAsync(5_000);
    expect(capture.getState()).toMatchObject({ status: "failed", reason: "audio_suspended" });
    expect(stream.track.stopped).toBe(true);
    expect(ends()).toHaveLength(1);
    expect(resolveResume).not.toBeNull();
  });

  it("C-PROMPT.voice a request that hangs is aborted after 10 s and retried", async () => {
    let hung = true;
    const hanging = vi.fn(async (input: string, init?: RequestInit) => {
      if (hung && String(input).includes("/voice/chunk")) {
        hung = false;
        return new Promise<Response>((_, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
        });
      }
      return fetchMock(input, init);
    });
    const { capture } = await recording({
      fetch: hanging as unknown as typeof fetch,
      requestTimeoutMs: 10_000,
    });
    speak(1);
    await settle();
    expect(chunks()).toHaveLength(0); // the first try hangs (the mock records only answered calls)
    await vi.advanceTimersByTimeAsync(10_000 + 600);
    expect(chunks().map((c) => c.seq)).toEqual([0]);
    expect(capture.getState().status).toBe("recording");
  });

  it("C-PROMPT.voice leaving without React's cleanup (pagehide) sends the last part second and end with keepalive", async () => {
    const { capture } = await recording();
    const node = nodes.at(-1)!;
    node.port.onmessage?.({ data: new Float32Array(24_000).fill(0.1) }); // half a second: not a full chunk yet
    await settle();
    fetchMock.mockClear();
    window.dispatchEvent(new Event("pagehide"));
    // Earlier tests' captures may still listen; this capture's own calls are the 0.5 s chunk and the end after it.
    const sent = fetchMock.mock.calls.map(([url, init]) => ({ url: String(url), init: init as RequestInit }));
    const chunkAt = sent.findIndex(
      (c) => c.url.includes("/voice/chunk?") && (c.init.body as Uint8Array).byteLength === 16_000, // 0.5 s
    );
    expect(chunkAt).toBeGreaterThanOrEqual(0);
    expect(sent[chunkAt]!.init).toMatchObject({ method: "POST", keepalive: true });
    const endAt = sent.findIndex((c, i) => i > chunkAt && c.url === `/api/drafts/${DRAFT}/voice/end`);
    expect(endAt).toBeGreaterThan(chunkAt);
    expect(sent[endAt]!.init).toMatchObject({ keepalive: true });
    expect(stream.track.stopped).toBe(true);
    expect(capture.getState().status).toBe("sending"); // then it reads the note back if the page is still here
  });

  it("C-PROMPT.voice the page hidden (phone locked, another app) ends the note the same way", async () => {
    await recording();
    fetchMock.mockClear();
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls.at(-1)).toBe(`/api/drafts/${DRAFT}/voice/end`);
    expect(stream.track.stopped).toBe(true);
  });

  it("C-PROMPT.voice leaving the screen flushes the last part second before end (dispose)", async () => {
    const { capture } = await recording();
    const node = nodes.at(-1)!;
    node.port.onmessage?.({ data: new Float32Array(48_000 + 12_000).fill(0.1) }); // 1.25 s
    await settle();
    fetchMock.mockClear();
    capture.dispose();
    const sent = fetchMock.mock.calls.map(([url, init]) => ({ url: String(url), init: init as RequestInit }));
    const lastChunk = sent.filter((c) => c.url.includes("/voice/chunk?")).at(-1)!;
    expect(lastChunk.init).toMatchObject({ keepalive: true });
    expect((lastChunk.init.body as Uint8Array).byteLength).toBe(8_000); // 0.25 s
    expect(sent.at(-1)!.url).toBe(`/api/drafts/${DRAFT}/voice/end`);
  });

  it("C-PROMPT.voice stop while the browser is still asking cancels, and the mic is let go when it arrives", async () => {
    let grant: ((s: FakeStream) => void) | null = null;
    getUserMedia.mockImplementationOnce(() => new Promise((r) => (grant = r)));
    const { capture } = make();
    const started = capture.start();
    expect(capture.getState().status).toBe("asking");
    capture.stop();
    expect(capture.getState().status).toBe("idle");
    grant!(stream);
    await started;
    await settle();
    expect(stream.track.stopped).toBe(true);
    expect(calls.filter((c) => c.path.endsWith("/voice/start"))).toHaveLength(0);
  });

  it("C-PROMPT.voice reset while asking cancels too", async () => {
    getUserMedia.mockImplementationOnce(() => new Promise(() => undefined));
    const { capture } = make();
    void capture.start();
    capture.reset();
    expect(capture.getState().status).toBe("idle");
  });

  it("L-DRAFT.voice a 409 chunk_out_of_order resyncs from details.next_seq instead of ending the note", async () => {
    let first = true;
    route = (call) => {
      if (call.path.endsWith("/voice/chunk") && first) {
        first = false;
        return { status: 409, body: { error: "chunk_out_of_order", details: { next_seq: 1 } } };
      }
      return defaultRoute(call);
    };
    const { capture } = await recording();
    speak(3);
    await settle();
    expect(capture.getState().status).toBe("recording");
    // seq 0 was already heard (next_seq 1): it is dropped, and 1 and 2 go on
    expect(chunks().map((c) => c.seq)).toEqual([0, 1, 2]);
  });

  it("L-DRAFT.voice a 409 with a gap renumbers what is left from next_seq", async () => {
    let refused = false;
    route = (call) => {
      if (call.path.endsWith("/voice/chunk") && call.seq === 1 && !refused) {
        refused = true; // the worker lost its place and asks for 0 again
        return { status: 409, body: { error: "chunk_out_of_order", details: { next_seq: 0 } } };
      }
      return defaultRoute(call);
    };
    const { capture } = await recording();
    speak(3);
    await settle();
    expect(chunks().map((c) => c.seq)).toEqual([0, 1, 0, 1]); // 1 and 2 go on as 0 and 1
    speak(1);
    await settle();
    expect(chunks().at(-1)!.seq).toBe(2); // and the next one follows them
    expect(capture.getState().status).toBe("recording");
  });

  it("L-DRAFT.voice a 429 with Retry-After waits that long before the retry", async () => {
    let first = true;
    const limited = vi.fn(async (input: string, init?: RequestInit) => {
      if (first && String(input).includes("/voice/chunk")) {
        first = false;
        calls.push({ method: "POST", path: "/limited" });
        return {
          ok: false,
          status: 429,
          headers: new Headers({ "Retry-After": "4" }),
          json: async () => ({}),
        } as Response;
      }
      return fetchMock(input, init);
    });
    await recording({ fetch: limited as unknown as typeof fetch, retryDelaysMs: [100, 100, 100] });
    speak(1);
    await settle();
    await vi.advanceTimersByTimeAsync(3_900);
    expect(chunks()).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(200);
    expect(chunks().map((c) => c.seq)).toEqual([0]);
  });

  it("L-DRAFT.voice retryAfterMs reads seconds or a date, capped at 10 s", () => {
    expect(retryAfterMs("4")).toBe(4_000);
    expect(retryAfterMs("120")).toBe(10_000);
    expect(retryAfterMs(new Date(5_000).toUTCString(), 2_000)).toBe(3_000);
    expect(retryAfterMs(null)).toBeUndefined();
    expect(retryAfterMs("soon")).toBeUndefined();
  });

  it("C-PROMPT.voice S-04 has no draft yet: resolveDraft is asked inside start, after the resume", async () => {
    const resolveDraft = vi.fn(async () => DRAFT);
    const capture = new VoiceCapture("", {
      fetch: fetchMock as unknown as typeof fetch,
      storage: memoryStorage(),
      device: "desktop",
      resolveDraft,
    });
    await capture.start();
    await settle();
    expect(resolveDraft).toHaveBeenCalledTimes(1);
    expect(calls[0]!.path).toBe(`/api/drafts/${DRAFT}/voice/start`);
    expect(capture.getState().status).toBe("recording");
  });
});
