// @vitest-environment jsdom
/**
 * BLD-B276, S-R3, C-PROMPT.voice: lane C's capture takes an optional `base` for its routes. With none, a draft's note
 * goes to `/api/drafts/{draft}/voice/start`, `/chunk`, `/end` and `/{stream}`, byte for byte as before; S-R3 passes
 * `/api/questions/{id}/answer/voice`, and the question id is the target, so no draft is asked for. The microphone and
 * the audio graph are fakes (lane C's harness, cut down); the URLs come through the `fetch` option. Synthetic only.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VoiceCapture, type VoiceCaptureOptions } from "@/lib/voice-capture";

const DRAFT = "6f1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a5b";
const QUESTION = "7a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d";
const STREAM = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d";

class FakeTrack {
  stop() {}
  addEventListener() {}
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
  constructor() {
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

const DONE = { id: STREAM, state: "done", seconds: 1, ended_by: "person", text: "Only our Hyderabad branch" };
let urls: string[] = [];

/** Every request's URL; `end` fails once so the capture also asks for the note's status (`GET {base}/{stream}`). */
const fetchMock = vi.fn(async (input: string) => {
  urls.push(input);
  const path = input.split("?")[0]!;
  if (path.endsWith("/end")) throw new TypeError("Failed to fetch");
  const body = path.endsWith("/start")
    ? { id: STREAM, state: "live" }
    : path.endsWith("/chunk")
      ? { id: STREAM, state: "live", next_seq: 1, seconds: 1, text: "Only our", spans: [] }
      : DONE;
  return { ok: true, status: path.endsWith("/start") ? 201 : 200, json: async () => body } as Response;
});

beforeEach(() => {
  vi.useFakeTimers();
  nodes = [];
  contexts = [];
  urls = [];
  fetchMock.mockClear();
  vi.stubGlobal("AudioContext", FakeContext);
  vi.stubGlobal("AudioWorkletNode", FakeNode);
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia: vi.fn(async () => new FakeStream()) },
    configurable: true,
  });
  URL.createObjectURL = vi.fn(() => "blob:voice-worklet");
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/** Start, one second of sound, then an interruption: `end` once (it fails), then the status poll. */
async function aNote(target: string, options: VoiceCaptureOptions = {}): Promise<string[]> {
  const resolveDraft = vi.fn(async () => "never-asked");
  const capture = new VoiceCapture(target, {
    fetch: fetchMock as unknown as typeof fetch,
    storage: null,
    device: "desktop",
    resolveDraft,
    ...options,
  });
  await capture.start();
  await vi.advanceTimersByTimeAsync(0);
  expect(capture.getState().status).toBe("recording");
  nodes.at(-1)!.port.onmessage?.({ data: new Float32Array(48_000).fill(0.1) });
  await vi.advanceTimersByTimeAsync(0);
  contexts.at(-1)!.becomes("interrupted");
  await vi.advanceTimersByTimeAsync(2000);
  expect(capture.getState().status).toBe("done");
  expect(resolveDraft).not.toHaveBeenCalled(); // the target is given: nothing tries to make a draft
  const paths = urls.map((u) => u.split("?")[0]!);
  capture.dispose();
  return paths;
}

describe("BLD-B276 C-PROMPT.voice: the capture's routes", () => {
  it("BLD-B276: with no `base`, a draft's note uses the draft's routes, as before", async () => {
    const paths = await aNote(DRAFT);
    expect(paths).toEqual([
      `/api/drafts/${DRAFT}/voice/start`,
      `/api/drafts/${DRAFT}/voice/chunk`,
      `/api/drafts/${DRAFT}/voice/end`,
      `/api/drafts/${DRAFT}/voice/${STREAM}`,
    ]);
    expect(urls[1]).toBe(`/api/drafts/${DRAFT}/voice/chunk?stream=${STREAM}&seq=0`);
  });

  it("BLD-B276, S-R3: with S-R3's `base`, an answer's note uses the question's routes", async () => {
    const base = `/api/questions/${encodeURIComponent(QUESTION)}/answer/voice`;
    const paths = await aNote(QUESTION, { base });
    expect(paths).toEqual([`${base}/start`, `${base}/chunk`, `${base}/end`, `${base}/${STREAM}`]);
    expect(urls[1]).toBe(`${base}/chunk?stream=${STREAM}&seq=0`);
  });
});
