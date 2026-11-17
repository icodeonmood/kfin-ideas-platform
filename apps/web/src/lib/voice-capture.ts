/**
 * "By voice" in the browser, without the look (L-DRAFT.voice, C-PROMPT.voice; DEC-108, BLD-C112, BLD-C118,
 * BLD-C119). Lane D draws the mic; S-04 drops `useVoiceCapture` (use-voice-capture.ts) into C-PROMPT.
 *
 * The flow: the person presses the mic → the browser asks for the microphone → POST …/voice/start → an AudioWorklet
 * hears the mic, the page downsamples to 16 kHz mono 16-bit PCM and sends one-second chunks to
 * …/voice/chunk?stream=&seq=, one at a time and in order, retrying a chunk that fails → each answer carries the words
 * so far (`text`, `spans` for the details others will not see) → stop, or 3 minutes, sends the last chunk and
 * POST …/voice/end → the person's words and the English copy. After a lost connection, an interruption or a pause
 * by the kill switch, the page polls GET …/voice/:stream until the worker has finished the note (it ends a stream
 * that has had no chunk for VOICE_IDLE_SECONDS and keeps what it heard).
 *
 * Audio is never stored: each chunk is dropped once the worker has answered for it. No text goes to the console.
 */
import { BANNERS } from "./killswitch-routes";
import { Downsampler, PcmChunker, toPcm16le, type PcmChunk } from "./voice-pcm";
import {
  isUuid,
  VOICE_EN_LABEL,
  VOICE_IDLE_SECONDS,
  VOICE_MAX_SECONDS,
  VOICE_NOTICE,
  VOICE_SAMPLE_RATE,
  type VoiceSpan,
} from "./voice-stream";
import { VOICE_WORKLET_NAME, voiceWorkletUrl } from "./voice-worklet";

export type VoiceDevice = "desktop" | "phone";

/** C-PROMPT.voice "Blocked", word for word from reference/copy/Compose.md and PhoneCompose.md, "State: Mic
 * blocked" (announced as an alert). */
export const MIC_BLOCKED: Record<VoiceDevice, { title: string; body: string }> = {
  desktop: {
    title: "Your browser has blocked the microphone.",
    body: "Allow it from the lock icon in the address bar, then try again. Or just type in the box above.",
  },
  phone: {
    title: "The microphone is off for this app.",
    body: "Turn it on in your phone’s settings, or type above. Your words save as you go.",
  },
};

/** C-PROMPT.voice "Listening" (Compose.md, PhoneCompose.md). */
export const VOICE_LISTENING = "Listening. Up to 3 minutes.";

export type VoiceEndedBy = "person" | "idle" | "limit" | "replaced" | "paused";

/** The finished note, for the person alone, until the draft takes it as a message (`streamId`). */
export type VoiceNote = {
  streamId: string;
  text: string; // their own words, as heard, in their language
  spans: VoiceSpan[];
  textEn: string | null; // null when the words were English, or the translation failed
  enLabel: string; // VOICE_EN_LABEL
  seconds: number;
  endedBy: VoiceEndedBy;
  hiddenCount: number;
  translated: boolean | null;
  translationFailure: string | null;
  lang: string | null;
  language: string | null;
  summary: string;
};

/** Codes, not copy: the pack draws no line for these (BLD-C119). */
export type VoiceFailure =
  | "not_supported" // no AudioWorklet or no getUserMedia (an old browser, or not https)
  | "no_microphone" // no device, or another app holds it
  | "signed_out"
  | "stream_lost" // the worker restarted, or the note never finished
  | "unavailable"
  | "audio_suspended" // the browser kept the audio context suspended (iOS outside a tap): the mic is released
  | (string & Record<never, never>); // the worker's own code: too_many_this_hour, not_a_draft, a failure code…

export type VoiceCaptureState =
  | { status: "idle"; notice: string | null }
  | { status: "asking" }
  | { status: "blocked"; device: VoiceDevice; title: string; body: string }
  | { status: "recording"; seconds: number; maxSeconds: number; text: string; spans: VoiceSpan[] }
  | { status: "sending"; seconds: number; text: string; spans: VoiceSpan[] }
  | { status: "done"; note: VoiceNote }
  | {
      status: "paused";
      banner: string; // the kill-switch answer's own banner (killswitch-routes BANNERS)
      switchName: string | null;
      text: string;
      spans: VoiceSpan[];
      note: VoiceNote | null; // the words kept, once the worker has finished the note
    }
  | { status: "failed"; reason: VoiceFailure; text: string; spans: VoiceSpan[] };

export type VoiceCaptureOptions = {
  device?: VoiceDevice;
  fetch?: typeof fetch;
  storage?: Pick<Storage, "getItem" | "setItem"> | null;
  retryDelaysMs?: readonly number[];
  pollMs?: number;
  pollForMs?: number;
  maxSeconds?: number;
  /** S-04 has no draft until the person speaks or types: asked for inside start(), after the audio context is made
   * and resumed in the tap, so the gesture is kept (BLD-C127). */
  resolveDraft?: () => Promise<string | null>;
  /** Each request is aborted after this long, so the retry and poll logic runs on a hung network (BLD-C127). */
  requestTimeoutMs?: number;
  /** The audio context must be running within this long of the tap, or the note fails with `audio_suspended`. */
  resumeTimeoutMs?: number;
};

export const VOICE_NOTICE_KEY = "1pc.voice.notice-seen";
const RETRY_DELAYS_MS = [500, 1500, 3000] as const;
const POLL_MS = 2000;
const REQUEST_TIMEOUT_MS = 10_000;
const RESUME_TIMEOUT_MS = 5_000;
const RETRY_AFTER_MAX_MS = 10_000;
/** Keepalive requests may carry 64 KB in all; the last chunks sent on leaving stay under it with room for `end`. */
const KEEPALIVE_BUDGET = 60_000;

type Answer = { ok: boolean; status: number; body: Record<string, unknown>; retryAfterMs?: number };
type Capture = {
  ctx: AudioContext;
  stream: MediaStream | null;
  node: AudioWorkletNode | null;
  source: MediaStreamAudioSourceNode | null;
};

const isObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown): string | null => (typeof v === "string" ? v : null);
const spansOf = (v: unknown): VoiceSpan[] =>
  Array.isArray(v)
    ? v.filter(
        (s): s is VoiceSpan =>
          isObject(s) &&
          typeof s.start === "number" &&
          typeof s.end === "number" &&
          typeof s.kind === "string",
      )
    : [];

function audioContextClass(): (new () => AudioContext) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    AudioContext?: new () => AudioContext;
    webkitAudioContext?: new () => AudioContext;
  };
  return w.AudioContext ?? w.webkitAudioContext ?? null;
}

export function detectDevice(): VoiceDevice {
  if (typeof navigator === "undefined") return "desktop";
  const nav = navigator as Navigator & { userAgentData?: { mobile?: boolean } };
  if (typeof nav.userAgentData?.mobile === "boolean") return nav.userAgentData.mobile ? "phone" : "desktop";
  return /Android|iPhone|iPad|iPod|Mobile/i.test(nav.userAgent) ? "phone" : "desktop";
}

function defaultStorage(): Pick<Storage, "getItem" | "setItem"> | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

/** A done view from the worker as the note the screen shows. */
export function toNote(view: Record<string, unknown>, streamId: string): VoiceNote {
  const ended = str(view.ended_by);
  return {
    streamId: str(view.id) ?? streamId,
    text: str(view.text) ?? "",
    spans: spansOf(view.spans),
    textEn: str(view.text_en),
    enLabel: VOICE_EN_LABEL,
    seconds: typeof view.seconds === "number" ? view.seconds : 0,
    endedBy:
      (["person", "idle", "limit", "replaced", "paused"] as const).find((e) => e === ended) ?? "person",
    hiddenCount: typeof view.hidden_count === "number" ? view.hidden_count : 0,
    translated: typeof view.translated === "boolean" ? view.translated : null,
    translationFailure: str(view.translation_failure),
    lang: str(view.lang),
    language: str(view.language),
    summary: str(view.summary) ?? "",
  };
}

export class VoiceCapture {
  private state: VoiceCaptureState;
  private readonly listeners = new Set<() => void>();
  private readonly fetchImpl: typeof fetch;
  private readonly storage: Pick<Storage, "getItem" | "setItem"> | null;
  private readonly device: VoiceDevice;
  private readonly retryDelays: readonly number[];
  private readonly pollMs: number;
  private readonly pollForMs: number;
  private readonly maxSeconds: number;
  private readonly resolveDraft: (() => Promise<string | null>) | null;
  private readonly requestTimeoutMs: number;
  private readonly resumeTimeoutMs: number;
  private target: string; // the draft the note belongs to: `draftId`, or the one `resolveDraft` gave
  private noticeShownOnScreen = false;
  private detach: (() => void) | null = null;

  private run = 0; // bumped by every start, reset and dispose: async work from an older run stops
  private capture: Capture | null = null;
  private streamId: string | null = null;
  private downsampler: Downsampler | null = null;
  private chunker = new PcmChunker();
  private queue: PcmChunk[] = [];
  private sending = false;
  private open = false; // the stream takes chunks
  private waiters: (() => void)[] = [];
  private samples = 0;
  private heard: { text: string; spans: VoiceSpan[] } = { text: "", spans: [] };
  private pollTimer: ReturnType<typeof setTimeout> | null = null;
  private inflight = new Set<AbortController>(); // aborted by reset and dispose: an old run's request stops

  constructor(
    readonly draftId: string,
    options: VoiceCaptureOptions = {},
  ) {
    this.fetchImpl = options.fetch ?? ((...a: Parameters<typeof fetch>) => fetch(...a));
    this.storage = options.storage === undefined ? defaultStorage() : options.storage;
    this.device = options.device ?? detectDevice();
    this.retryDelays = options.retryDelaysMs ?? RETRY_DELAYS_MS;
    this.pollMs = options.pollMs ?? POLL_MS;
    this.pollForMs = options.pollForMs ?? (VOICE_IDLE_SECONDS + 300) * 1000;
    this.maxSeconds = options.maxSeconds ?? VOICE_MAX_SECONDS;
    this.resolveDraft = options.resolveDraft ?? null;
    this.requestTimeoutMs = options.requestTimeoutMs ?? REQUEST_TIMEOUT_MS;
    this.resumeTimeoutMs = options.resumeTimeoutMs ?? RESUME_TIMEOUT_MS;
    this.target = draftId;
    this.state = this.idle();
  }

  readonly getState = (): VoiceCaptureState => this.state;

  readonly subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  /** The screen has shown VOICE_NOTICE: only then does the first recording mark it seen on this device. */
  readonly noticeShown = (): void => {
    this.noticeShownOnScreen = true;
  };

  /** The person pressed the mic. Call it from the click handler: the audio context is made and resumed inside the
   * gesture, before anything is awaited, or iOS Safari keeps it suspended (BLD-C127). */
  readonly start = async (): Promise<void> => {
    const s = this.state.status;
    if (s === "asking" || s === "recording" || s === "sending") return;
    const run = this.begin();
    const AC = audioContextClass();
    const media = typeof navigator !== "undefined" ? navigator.mediaDevices : undefined;
    if (!AC || typeof AudioWorkletNode === "undefined" || typeof media?.getUserMedia !== "function")
      return this.fail("not_supported");
    let ctx: AudioContext;
    try {
      ctx = new AC();
    } catch {
      return this.fail("not_supported");
    }
    const capture: Capture = { ctx, stream: null, node: null, source: null };
    this.capture = capture;
    // Still inside the tap: watch the context, and ask it to run, before the first await.
    ctx.addEventListener("statechange", () => {
      const st = ctx.state as string;
      if (st === "suspended" || st === "interrupted") this.interrupted(run);
    });
    const resumed = this.resumeWithin(ctx);
    this.set({ status: "asking" });

    try {
      capture.stream = await media.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (err) {
      if (run !== this.run) return;
      this.release();
      const name = typeof err === "object" && err !== null && "name" in err ? String(err.name) : "";
      if (name === "NotAllowedError" || name === "SecurityError" || name === "PermissionDeniedError")
        return this.set({ status: "blocked", device: this.device, ...MIC_BLOCKED[this.device] });
      return this.fail(
        name === "NotFoundError" || name === "NotReadableError" || name === "OverconstrainedError"
          ? "no_microphone"
          : "not_supported",
      );
    }
    if (run !== this.run) return stopTracks(capture.stream); // cancelled while asking

    try {
      await ctx.audioWorklet.addModule(voiceWorkletUrl());
      if (run !== this.run) return;
      capture.node = new AudioWorkletNode(ctx, VOICE_WORKLET_NAME, {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        outputChannelCount: [1],
      });
      capture.source = ctx.createMediaStreamSource(capture.stream);
      this.downsampler = new Downsampler(ctx.sampleRate);
    } catch {
      if (run !== this.run) return;
      this.release();
      return this.fail("not_supported");
    }

    if (!this.target && this.resolveDraft) {
      const got = await this.resolveDraft().catch(() => null);
      if (run !== this.run) return;
      if (!got) {
        this.release();
        return this.fail("unavailable");
      }
      this.target = got;
    }

    const opened = await this.call("POST", "start");
    if (run !== this.run) {
      if (opened.ok && isUuid(opened.body.id)) void this.endQuietly(opened.body.id);
      return;
    }
    if (!opened.ok || !isUuid(opened.body.id)) {
      this.release();
      return opened.ok ? this.fail("unavailable") : this.refused(run, opened);
    }
    this.streamId = opened.body.id;
    this.open = true;

    const { node, source, stream } = capture;
    if (!node || !source || !stream) return this.fail("not_supported");
    node.port.onmessage = (e: MessageEvent) => this.hear(run, e.data);
    source.connect(node);
    node.connect(ctx.destination); // pulls the graph; the worklet writes silence, so nothing is heard
    for (const track of stream.getAudioTracks()) track.addEventListener("ended", () => this.interrupted(run));
    this.watchLeaving(run);
    if (this.noticeShownOnScreen) this.noticeSeen();
    // Recording before the resume settles, so no audio the worklet sends is dropped.
    this.set({ status: "recording", seconds: 0, maxSeconds: this.maxSeconds, text: "", spans: [] });
    const running = await resumed;
    // Stopped, ended or left while the resume was settling: that path owns the note, and its end is already sent.
    if (run !== this.run || running || this.state.status !== "recording") return;
    // The context never ran (iOS outside the tap): the mic goes off, the note ends, and the reason is a code.
    const id = this.streamId;
    this.release();
    this.open = false;
    this.queue = [];
    if (id) void this.endQuietly(id);
    this.fail("audio_suspended");
  };

  /** ctx.resume(), called now; true once the context runs, false if it is still suspended after the timeout. */
  private resumeWithin(ctx: AudioContext): Promise<boolean> {
    let asked: Promise<unknown>;
    try {
      asked = Promise.resolve(ctx.resume());
    } catch {
      asked = Promise.resolve();
    }
    let timer: ReturnType<typeof setTimeout> | null = null;
    const timeout = new Promise<boolean>((resolve) => {
      timer = setTimeout(() => resolve((ctx.state as string) === "running"), this.resumeTimeoutMs);
    });
    const done = asked.then(
      () => (ctx.state as string) !== "suspended",
      () => (ctx.state as string) === "running",
    );
    return Promise.race([done, timeout]).finally(() => {
      if (timer !== null) clearTimeout(timer);
    });
  }

  /** Leaving without React's cleanup (a closed tab, a locked phone, another app): the last seconds and the end go
   * with keepalive, then the page reads the note back if it is still there (BLD-C127). */
  private watchLeaving(run: number): void {
    if (typeof window === "undefined") return;
    const gone = () => this.leaving(run);
    const hidden = () => {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") this.leaving(run);
    };
    window.addEventListener("pagehide", gone);
    document.addEventListener("visibilitychange", hidden);
    this.detach = () => {
      window.removeEventListener("pagehide", gone);
      document.removeEventListener("visibilitychange", hidden);
    };
  }

  private leaving(run: number): void {
    if (run !== this.run || !this.open || !this.streamId) return;
    const s = this.state.status;
    if (s !== "recording" && s !== "sending") return;
    this.release();
    this.sendLastQuietly(this.streamId);
    this.open = false;
    this.queue = [];
    this.wake();
    this.set({ status: "sending", seconds: this.seconds(), ...this.heard });
    this.poll(run);
  }

  /** The chunks still here, the last part second included, then `end`, all with keepalive and under its budget. */
  private sendLastQuietly(stream: string): void {
    const last = this.chunker.flush();
    if (last) this.queue.push(last);
    let budget = KEEPALIVE_BUDGET;
    for (const chunk of this.queue) {
      if (chunk.data.byteLength > budget) break;
      budget -= chunk.data.byteLength;
      const q = new URLSearchParams({ stream, seq: String(chunk.seq) });
      try {
        void this.fetchImpl(`/api/drafts/${encodeURIComponent(this.target)}/voice/chunk?${q}`, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/octet-stream" },
          body: chunk.data,
          keepalive: true,
        }).catch(() => undefined);
      } catch {
        // the page is going; the worker keeps what it had
      }
    }
    this.queue = [];
    void this.endQuietly(stream);
  }

  /** The person pressed stop. While the browser is still asking for the mic, stop cancels. */
  readonly stop = (): void => {
    if (this.state.status === "asking") {
      this.begin();
      this.set(this.idle());
      return;
    }
    void this.finish(this.run, "person");
  };

  /** Back to idle once the screen has taken the note, or to try again after blocked, paused or failed. */
  readonly reset = (): void => {
    const s = this.state.status;
    if (s === "recording" || s === "sending") return; // asking can be cancelled
    this.begin();
    this.set(this.idle());
  };

  /** The screen is going away. A note still being made is ended (its words are kept for the draft, J-RESUME/1);
   * if that cannot be sent, the worker ends it after VOICE_IDLE_SECONDS anyway. */
  readonly dispose = (): void => {
    const live = this.open && this.streamId !== null;
    const id = this.streamId;
    if (live && id) this.sendLastQuietly(id); // the last part second first, then end (BLD-C127)
    this.begin();
    this.set(this.idle());
  };

  // ── the audio ──────────────────────────────────────────────────────────────────────────────────────────────

  private hear(run: number, data: unknown): void {
    if (run !== this.run || this.state.status !== "recording" || !this.downsampler) return;
    if (!(data instanceof Float32Array)) return;
    const max = this.maxSeconds * VOICE_SAMPLE_RATE;
    let out = this.downsampler.push(data);
    if (out.length > max - this.samples) out = out.subarray(0, Math.max(0, max - this.samples));
    this.samples += out.length;
    this.queue.push(...this.chunker.push(toPcm16le(out)));
    void this.pump(run);
    const seconds = Math.floor(this.samples / VOICE_SAMPLE_RATE);
    if (this.state.status === "recording" && seconds !== this.state.seconds)
      this.set({ ...this.state, seconds });
    if (this.samples >= max) void this.finish(run, "limit");
  }

  private interrupted(run: number): void {
    if (run === this.run && this.state.status === "recording") void this.finish(run, "interrupted");
  }

  private async finish(run: number, why: "person" | "limit" | "interrupted"): Promise<void> {
    if (run !== this.run || this.state.status !== "recording") return;
    this.release(); // the mic goes off at once
    const last = this.chunker.flush();
    if (last) this.queue.push(last);
    this.set({ status: "sending", seconds: this.seconds(), ...this.heard });
    void this.pump(run);
    await this.drained(run);
    if (run !== this.run || !this.open || !this.streamId) return;
    this.open = false;
    const end = () => this.call("POST", "end", { stream: this.streamId });
    // An interruption (the phone locked, the mic was taken) may leave no time to retry: one try, then the poll.
    const answer = why === "interrupted" ? await end() : await this.retrying(run, end);
    if (run !== this.run) return;
    if (answer.ok && answer.body.state !== "live") return this.settle(run, answer.body);
    if (answer.ok) return this.poll(run);
    this.refused(run, answer);
  }

  private release(): void {
    this.detach?.();
    this.detach = null;
    const c = this.capture;
    this.capture = null;
    if (!c) return;
    try {
      c.source?.disconnect();
      c.node?.disconnect();
      if (c.node) c.node.port.onmessage = null;
    } catch {
      // already disconnected
    }
    stopTracks(c.stream);
    try {
      void Promise.resolve(c.ctx.close()).catch(() => undefined);
    } catch {
      // already closed
    }
  }

  // ── the chunks ─────────────────────────────────────────────────────────────────────────────────────────────

  private async pump(run: number): Promise<void> {
    if (this.sending) return;
    this.sending = true;
    try {
      while (run === this.run && this.open && this.streamId && this.queue.length > 0) {
        const chunk = this.queue[0]!;
        const answer = await this.retrying(run, () => this.call("POST", "chunk", chunk));
        if (run !== this.run || !this.open) return;
        if (!answer.ok && this.resync(answer)) continue;
        if (!answer.ok) {
          this.queue = [];
          return this.refused(run, answer);
        }
        this.queue.shift(); // answered: the audio is dropped
        if (answer.body.state === "live") this.words(answer.body);
        else return this.settle(run, answer.body); // the worker ended it: 3 minutes, idle, or replaced
      }
    } finally {
      if (run === this.run) {
        this.sending = false; // a newer run's sender is its own
        if (this.queue.length === 0 || !this.open) this.wake();
      }
    }
  }

  /** A 409 chunk_out_of_order with the worker's `next_seq`: drop what it already has, renumber the rest from there,
   * and carry on, instead of ending the note (BLD-C127). False when there is nothing to resync from. */
  private resync(answer: Answer): boolean {
    if (answer.status !== 409 || answer.body.error !== "chunk_out_of_order") return false;
    const details = isObject(answer.body.details) ? answer.body.details : answer.body;
    const next = details.next_seq;
    if (typeof next !== "number" || !Number.isInteger(next) || next < 0) return false;
    const head = this.queue[0];
    if (!head) return false;
    if (head.seq < next) {
      this.queue = this.queue.filter((c) => c.seq >= next); // already heard
    } else {
      this.queue = this.queue.map((c, i) => ({ ...c, seq: next + i })); // a gap: go on from where it is
    }
    this.chunker.continueFrom(Math.max(next, (this.queue.at(-1)?.seq ?? next - 1) + 1));
    return true;
  }

  private drained(run: number): Promise<void> {
    if (run !== this.run || !this.open || (!this.sending && this.queue.length === 0))
      return Promise.resolve();
    return new Promise((resolve) => this.waiters.push(resolve));
  }

  private wake(): void {
    const waiters = this.waiters;
    this.waiters = [];
    for (const w of waiters) w();
  }

  private async retrying(run: number, send: () => Promise<Answer>): Promise<Answer> {
    let answer = await send();
    for (const delay of this.retryDelays) {
      if (answer.ok || !retryable(answer) || run !== this.run) return answer;
      await sleep(answer.retryAfterMs ?? delay); // 429, or a busy 503, may say how long to wait
      if (run !== this.run) return answer;
      answer = await send();
    }
    return answer;
  }

  private async call(
    method: "GET" | "POST",
    what: string,
    body?: PcmChunk | { stream: unknown },
  ): Promise<Answer> {
    const draft = encodeURIComponent(this.target);
    let url = `/api/drafts/${draft}/voice/${what}`;
    const abort = new AbortController();
    this.inflight.add(abort);
    const init: RequestInit = { method, credentials: "same-origin", cache: "no-store", signal: abort.signal };
    if (body && "seq" in body) {
      url += `?${new URLSearchParams({ stream: this.streamId ?? "", seq: String(body.seq) })}`;
      init.headers = { "Content-Type": "application/octet-stream" };
      init.body = body.data;
    } else if (body) {
      init.headers = { "Content-Type": "application/json" };
      init.body = JSON.stringify(body);
    }
    // A hung request is given up after requestTimeoutMs, so the retry and poll logic runs (BLD-C127).
    const timer = setTimeout(() => abort.abort(), this.requestTimeoutMs);
    try {
      const res = await this.fetchImpl(url, init);
      const data: unknown = await res.json().catch(() => ({}));
      const answer: Answer = { ok: res.ok, status: res.status, body: isObject(data) ? data : {} };
      const after =
        res.status === 429 || res.status === 503
          ? retryAfterMs(res.headers?.get?.("Retry-After") ?? null)
          : undefined;
      if (after !== undefined) answer.retryAfterMs = after;
      return answer;
    } catch {
      return { ok: false, status: 0, body: {} }; // offline, timed out, or the connection dropped
    } finally {
      clearTimeout(timer);
      this.inflight.delete(abort);
    }
  }

  private async endQuietly(stream: string): Promise<void> {
    const draft = encodeURIComponent(this.target);
    try {
      await this.fetchImpl(`/api/drafts/${draft}/voice/end`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stream }),
        keepalive: true,
      });
    } catch {
      // the worker ends it after VOICE_IDLE_SECONDS and keeps the words
    }
  }

  // ── answers ────────────────────────────────────────────────────────────────────────────────────────────────

  /** The words so far, from a chunk's answer or a poll. */
  private words(view: Record<string, unknown>): void {
    this.heard = { text: str(view.text) ?? this.heard.text, spans: spansOf(view.spans) };
    const s = this.state;
    if (s.status === "recording" || s.status === "sending") this.set({ ...s, ...this.heard });
    else if (s.status === "paused" && !s.note) this.set({ ...s, ...this.heard });
  }

  /** A finished view: done, failed, handed or expired. */
  private settle(run: number, view: Record<string, unknown>): void {
    if (run !== this.run) return;
    this.release();
    this.open = false;
    this.queue = [];
    this.clearPoll();
    this.wake();
    const id = this.streamId ?? "";
    const s = this.state;
    if (s.status === "paused") {
      return this.set({ ...s, note: view.state === "done" ? toNote(view, id) : null });
    }
    if (view.state === "done") {
      const note = toNote(view, id);
      return this.set({ status: "done", note });
    }
    this.fail(
      view.state === "failed" ? (str(view.failure) ?? "unavailable") : (str(view.state) ?? "unavailable"),
    );
  }

  /** A refused or failed request. */
  private refused(run: number, answer: Answer): void {
    if (run !== this.run) return;
    const code = str(answer.body.error);
    const details = isObject(answer.body.details) ? answer.body.details : null;
    if (answer.status === 503 && (code === "paused" || code === "voice_paused")) {
      // The proxy's kill-switch answer carries its banner; the worker's own check (speech.hosted read fresh) has
      // none, so it is that switch's banner from the same table.
      this.release();
      this.open = false;
      this.queue = [];
      this.wake();
      this.set({
        status: "paused",
        banner: str(answer.body.banner) ?? BANNERS["speech.hosted"],
        switchName: str(answer.body.switch) ?? (code === "voice_paused" ? "speech.hosted" : null),
        ...this.heard,
        note: null,
      });
      if (details && details.state) return this.settle(run, details); // the worker ended it, words kept
      if (this.streamId) this.poll(run); // reading the note is not paused (killswitch-routes)
      return;
    }
    if (answer.status === 409 && code === "stream_ended" && details) return this.settle(run, details);
    if (answer.status === 401) return this.stopWith("signed_out");
    if (answer.status === 410) return this.stopWith("stream_lost");
    const lost =
      retryable(answer) ||
      (answer.status === 409 && (code === "chunk_out_of_order" || code === "stream_ending"));
    if (lost && this.streamId) {
      // A dropped connection: the mic goes off and the worker finishes the note on its own; read it back.
      this.release();
      this.open = false;
      this.queue = [];
      this.wake();
      if (this.state.status === "recording")
        this.set({ status: "sending", seconds: this.seconds(), ...this.heard });
      return this.poll(run);
    }
    this.stopWith(code ?? "unavailable"); // the worker's own code when it gave one (too_many_this_hour…)
  }

  private stopWith(reason: VoiceFailure): void {
    this.release();
    this.open = false;
    this.queue = [];
    this.clearPoll();
    this.wake();
    if (this.state.status === "paused") return; // the banner stays; the note could not be read back
    this.fail(reason);
  }

  // ── polling ────────────────────────────────────────────────────────────────────────────────────────────────

  private poll(run: number, until: number = Date.now() + this.pollForMs): void {
    this.clearPoll();
    const id = this.streamId;
    if (!id) return;
    this.pollTimer = setTimeout(() => {
      this.pollTimer = null;
      void (async () => {
        const answer = await this.call("GET", encodeURIComponent(id));
        if (run !== this.run) return;
        const view = answer.ok
          ? answer.body
          : answer.status === 409 && isObject(answer.body.details)
            ? answer.body.details
            : null;
        if (view && view.state === "live") {
          this.words(view);
        } else if (view) {
          return this.settle(run, view);
        } else if (answer.status === 401) {
          return this.stopWith("signed_out");
        } else if (answer.status === 404 || answer.status === 410) {
          return this.stopWith("stream_lost");
        }
        if (Date.now() >= until) return this.stopWith("stream_lost");
        this.poll(run, until); // still live, offline, or the server is busy: ask again
      })();
    }, this.pollMs);
  }

  private clearPoll(): void {
    if (this.pollTimer !== null) clearTimeout(this.pollTimer);
    this.pollTimer = null;
  }

  // ── state ──────────────────────────────────────────────────────────────────────────────────────────────────

  private begin(): number {
    this.run += 1;
    for (const a of this.inflight) a.abort(); // the older run's requests stop; their answers are ignored anyway
    this.inflight.clear();
    this.release();
    this.clearPoll();
    this.wake();
    this.streamId = null;
    this.open = false;
    this.queue = [];
    this.sending = false;
    this.samples = 0;
    this.downsampler = null;
    this.chunker = new PcmChunker();
    this.heard = { text: "", spans: [] };
    return this.run;
  }

  private idle(): VoiceCaptureState {
    let seen = false;
    try {
      seen = this.storage?.getItem(VOICE_NOTICE_KEY) === "1";
    } catch {
      seen = false; // storage blocked: the notice shows every time
    }
    return { status: "idle", notice: seen ? null : VOICE_NOTICE };
  }

  private noticeSeen(): void {
    try {
      this.storage?.setItem(VOICE_NOTICE_KEY, "1");
    } catch {
      // storage blocked: the notice shows again next time
    }
  }

  private seconds(): number {
    return Math.floor(this.samples / VOICE_SAMPLE_RATE);
  }

  private fail(reason: VoiceFailure): void {
    this.set({ status: "failed", reason, ...this.heard });
  }

  private set(next: VoiceCaptureState): void {
    this.state = next;
    for (const listener of [...this.listeners]) listener();
  }
}

/** Retry-After in seconds or as a date, as milliseconds to wait, capped; undefined when absent or unreadable. */
export function retryAfterMs(value: string | null, now: number = Date.now()): number | undefined {
  if (!value) return undefined;
  const v = value.trim();
  const ms = /^\d+$/.test(v) ? Number(v) * 1000 : Date.parse(v) - now;
  if (!Number.isFinite(ms)) return undefined;
  return Math.min(RETRY_AFTER_MAX_MS, Math.max(0, ms));
}

function retryable(a: Answer): boolean {
  if (a.status === 503) return a.body.error !== "paused" && a.body.error !== "voice_paused";
  return (
    a.status === 0 ||
    a.status === 408 ||
    a.status === 429 ||
    a.status === 500 ||
    a.status === 502 ||
    a.status === 504
  );
}

function stopTracks(stream: MediaStream | null): void {
  for (const track of stream?.getTracks() ?? []) track.stop();
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));
