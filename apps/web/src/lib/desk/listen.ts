/**
 * The speech engine behind the review desk's "Listen to the whole idea" player (C-LISTEN, L-LISTEN).
 *
 * BLD-B230: there is no audio file. The browser's own speech engine reads the masked script on the device,
 * one utterance per part, with a local voice only. Part start times are estimated from the text length; the
 * clock and the chapter ticks always show the 1× timeline, and faster speeds move along it faster.
 *
 * Framework-free, so the player component can wrap it. The synth, the utterance constructor and the clock
 * are injected, which is how the tests drive it without a browser.
 */

export const PART_IDS = ["summary", "often", "who", "cost", "evidence", "fix"] as const;
export type ListenPartId = (typeof PART_IDS)[number];
export type ListenPart = { part: ListenPartId; title: string; text: string };
/** The six parts in the idea's order, already masked by the server. */
export type ListenScript = { parts: ListenPart[] };

/** About how many characters a voice reads in a second at 1×. Every estimate starts here. */
export const CHARS_PER_SECOND = 15;
/** The short pause between one part and the next, in seconds. Not scaled by speed. */
export const PART_GAP_SECONDS = 0.5;
export const SPEEDS = [1, 1.25, 1.5, 2] as const;
export type ListenRate = (typeof SPEEDS)[number];
/** L-LISTEN/5: a script saved for offline is kept this many days. */
export const OFFLINE_DAYS = 30;
/** L-LISTEN/7: what the player shows when the speech engine fails. */
export const LISTEN_ERROR = "Couldn't prepare the audio. Try again.";

const TICK_MS = 250;
// Float sums land a hair under whole numbers (129.99999…); this keeps them on the right side.
const EPSILON = 1e-6;

// ---------------------------------------------------------------------------------------------------------
// What the engine needs from the browser. `speechSynthesis`, `SpeechSynthesisUtterance` and the voices from
// `getVoices()` fit these shapes as they are.

export interface ListenVoice {
  readonly lang: string;
  readonly localService: boolean;
}

export interface ListenUtterance {
  rate: number;
  lang: string;
  voice: ListenVoice | null;
  addEventListener(type: "boundary", listener: (event: { charIndex: number }) => void): void;
  addEventListener(type: "end", listener: () => void): void;
  addEventListener(type: "error", listener: (event: { error: string }) => void): void;
}

export type ListenUtteranceCtor = new (text: string) => ListenUtterance;

export interface ListenSynth {
  speak(utterance: ListenUtterance): void;
  cancel(): void;
}

// ---------------------------------------------------------------------------------------------------------
// Voice

/** The best local English voice: Indian English first, then any English. Null hides the player (BLD-B230). */
export function pickVoice<V extends ListenVoice>(voices: readonly V[]): V | null {
  const local = voices.filter((v) => v.localService);
  // Some Android builds report "en_IN".
  const lang = (v: V) => v.lang.replace("_", "-").toLowerCase();
  return local.find((v) => lang(v) === "en-in") ?? local.find((v) => /^en(-|$)/.test(lang(v))) ?? null;
}

// ---------------------------------------------------------------------------------------------------------
// Timeline

export type ListenMark = { part: ListenPartId; title: string; start: number; length: number };
export type ListenTimeline = { parts: ListenMark[]; total: number };

/** What is spoken for a part: its title as a heading, then its text. */
export function spokenText(part: ListenPart): string {
  const text = part.text.trim();
  return text ? `${part.title}. ${text}` : `${part.title}.`;
}

/** Each part's start second and length, and the total, at a speed. Rate 1 gives the clock and the ticks. */
export function estimate(script: ListenScript, rate: number = 1): ListenTimeline {
  const speed = rate > 0 ? rate : 1;
  const parts: ListenMark[] = [];
  let at = 0;
  script.parts.forEach((p, i) => {
    if (i > 0) at += PART_GAP_SECONDS;
    const length = spokenText(p).length / (CHARS_PER_SECOND * speed);
    parts.push({ part: p.part, title: p.title, start: at, length });
    at += length;
  });
  return { parts, total: at };
}

// ---------------------------------------------------------------------------------------------------------
// Words for the screen and for screen readers (C-LISTEN.behaviour/7)

function wholeSeconds(seconds: number): number {
  return Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds + EPSILON)) : 0;
}

/** "2:10". */
export function clock(seconds: number): string {
  const s = wholeSeconds(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** "2 minutes 10 seconds", "1 minute", "45 seconds". */
function lengthInWords(seconds: number): string {
  const s = wholeSeconds(seconds);
  const minutes = Math.floor(s / 60);
  const rest = s % 60;
  const words: string[] = [];
  if (minutes > 0) words.push(`${minutes} ${minutes === 1 ? "minute" : "minutes"}`);
  if (rest > 0 || minutes === 0) words.push(`${rest} ${rest === 1 ? "second" : "seconds"}`);
  return words.join(" ");
}

export function playLabel(total: number): string {
  return `Play the whole idea, ${lengthInWords(total)}`;
}

export function progressLabel(position: number, total: number): string {
  return `Played ${clock(position)} of ${clock(total)}`;
}

export function jumpLabel(title: string, at: number): string {
  return `Jump to ${title}, ${clock(at)}`;
}

export function nowLabel(title: string): string {
  return `Now: ${title}`;
}

// ---------------------------------------------------------------------------------------------------------
// Engine

export type ListenState = Readonly<{
  playing: boolean;
  /** Seconds on the 1× timeline. */
  position: number;
  total: number;
  currentPart: ListenPartId | null;
  rate: ListenRate;
  /** The speech engine failed; the player shows LISTEN_ERROR. Cleared by the next play(). */
  error: boolean;
}>;

export type ListenListener = (state: ListenState) => void;

export interface ListenEngineOptions {
  synth: ListenSynth;
  Utterance: ListenUtteranceCtor;
  script: ListenScript;
  voice: ListenVoice;
  /** Milliseconds, for the clock fallback. Defaults to performance.now. */
  now?: () => number;
  /** Calls fn every ms until the returned stop is called. Defaults to setInterval. */
  every?: (fn: () => void, ms: number) => () => void;
}

type Segment = { mark: ListenMark; text: string };

function isSpace(c: string | undefined): boolean {
  return c === undefined || /\s/.test(c);
}

/** The start of the word at or before index i. */
function wordStart(text: string, i: number): number {
  let at = Math.max(0, Math.min(i, text.length - 1));
  while (at > 0 && !(!isSpace(text[at]) && isSpace(text[at - 1]))) at -= 1;
  return at;
}

export class ListenEngine {
  /** The 1× timeline: chapter ticks, the parts menu and the clock. */
  readonly timeline: ListenTimeline;

  private readonly synth: ListenSynth;
  private readonly Utterance: ListenUtteranceCtor;
  private readonly voice: ListenVoice;
  private readonly now: () => number;
  private readonly every: (fn: () => void, ms: number) => () => void;
  private readonly segments: Segment[];
  private readonly listeners = new Set<ListenListener>();

  private playing = false;
  private error = false;
  private disposed = false;
  private rate: ListenRate = 1;
  private index = 0;
  private position = 0;
  // Bumped for every utterance spoken and on every stop; events carrying an older number are ignored.
  private generation = 0;
  private sawBoundary = false;
  private anchor = { position: 0, at: 0 };
  private stopTick: (() => void) | null = null;
  private snapshot: ListenState;

  constructor(options: ListenEngineOptions) {
    this.synth = options.synth;
    this.Utterance = options.Utterance;
    this.voice = options.voice;
    this.now = options.now ?? (() => performance.now());
    this.every =
      options.every ??
      ((fn, ms) => {
        const handle = setInterval(fn, ms);
        return () => clearInterval(handle);
      });
    this.timeline = estimate(options.script, 1);
    this.segments = this.timeline.parts.map((mark, i) => {
      const part = options.script.parts[i];
      return { mark, text: part ? spokenText(part) : "" };
    });
    this.snapshot = this.makeState();
  }

  state(): ListenState {
    return this.snapshot;
  }

  /** Calls the listener now and on every change. Returns the unsubscribe. */
  subscribe(listener: ListenListener): () => void {
    this.listeners.add(listener);
    listener(this.snapshot);
    return () => {
      this.listeners.delete(listener);
    };
  }

  play(): void {
    if (this.disposed || this.playing || this.segments.length === 0) return;
    this.playing = true;
    this.error = false;
    this.restart(this.index, this.offsetIn(this.index, this.position));
    this.startTicking();
    this.emit();
  }

  pause(): void {
    if (!this.playing) return;
    this.syncClock();
    this.halt();
    this.synth.cancel();
    this.emit();
  }

  toggle(): void {
    if (this.playing) this.pause();
    else this.play();
  }

  /** Moves to a second on the 1× timeline, at the start of the word there; keeps playing if it was. */
  seek(seconds: number): void {
    if (this.disposed || this.segments.length === 0) return;
    const target = Math.max(0, Math.min(Number.isFinite(seconds) ? seconds : 0, this.timeline.total));
    if (target > 0 && target >= this.timeline.total - EPSILON) {
      this.finish(this.playing);
      return;
    }
    const { index, offset } = this.locate(target);
    this.index = index;
    this.position = this.positionOf(index, offset);
    if (this.playing) this.restart(index, offset);
    this.emit();
  }

  jumpTo(part: ListenPartId): void {
    const segment = this.segments.find((s) => s.mark.part === part);
    if (segment) this.seek(segment.mark.start);
  }

  /** 1× → 1.25× → 1.5× → 2× → 1×. Mid-part it re-speaks from the current word at the new speed. */
  cycleSpeed(): void {
    if (this.disposed) return;
    const at = SPEEDS.indexOf(this.rate);
    this.rate = SPEEDS[(at + 1) % SPEEDS.length] ?? 1;
    if (this.playing) {
      this.syncClock();
      this.restart(this.index, this.offsetIn(this.index, this.position));
    }
    this.emit();
  }

  dispose(): void {
    if (this.disposed) return;
    const wasPlaying = this.playing;
    this.disposed = true;
    this.halt();
    if (wasPlaying) this.synth.cancel();
    this.listeners.clear();
  }

  // -------------------------------------------------------------------------------------------------------

  private restart(index: number, offset: number): void {
    // The browser cannot start mid-utterance, so stop and speak a new one from the offset.
    this.generation += 1;
    this.synth.cancel();
    this.speak(index, offset);
  }

  private speak(index: number, offset: number): void {
    const generation = ++this.generation;
    const text = this.segments[index]?.text ?? "";
    const utterance = new this.Utterance(text.slice(offset));
    utterance.voice = this.voice;
    utterance.lang = this.voice.lang;
    utterance.rate = this.rate;
    utterance.addEventListener("boundary", (event) =>
      this.onBoundary(generation, index, offset, event.charIndex),
    );
    utterance.addEventListener("end", () => this.onEnd(generation, index));
    utterance.addEventListener("error", (event) => this.onError(generation, event.error));
    this.index = index;
    this.position = this.positionOf(index, offset);
    this.sawBoundary = false;
    this.anchor = { position: this.position, at: this.now() };
    this.synth.speak(utterance);
  }

  private onBoundary(generation: number, index: number, offset: number, charIndex: number): void {
    if (generation !== this.generation) return;
    this.sawBoundary = true;
    const length = this.segments[index]?.text.length ?? 0;
    this.position = this.positionOf(index, Math.min(length, offset + Math.max(0, charIndex)));
    this.emit();
  }

  private onEnd(generation: number, index: number): void {
    if (generation !== this.generation) return;
    if (index + 1 < this.segments.length) {
      this.speak(index + 1, 0);
      this.emit();
    } else {
      this.finish(false);
    }
  }

  private onError(generation: number, code: string): void {
    if (generation !== this.generation) return;
    // Something else on the page stopped the speech: that is a pause, not a failure.
    if (code === "interrupted" || code === "canceled") {
      this.syncClock();
    } else {
      this.error = true;
    }
    this.halt();
    this.emit();
  }

  /** C-LISTEN.behaviour/5: at the end, stop and go back to 0:00. */
  private finish(cancel: boolean): void {
    this.halt();
    if (cancel) this.synth.cancel();
    this.index = 0;
    this.position = 0;
    this.emit();
  }

  private halt(): void {
    this.playing = false;
    this.generation += 1;
    this.stopTick?.();
    this.stopTick = null;
  }

  private startTicking(): void {
    if (this.stopTick) return;
    this.stopTick = this.every(() => {
      const before = this.position;
      this.syncClock();
      if (this.position !== before) this.emit();
    }, TICK_MS);
  }

  /** The clock fallback, for voices that send no boundary events: elapsed time × speed, held to the part. */
  private syncClock(): void {
    if (!this.playing || this.sawBoundary) return;
    const segment = this.segments[this.index];
    if (!segment) return;
    const elapsed = (Math.max(0, this.now() - this.anchor.at) / 1000) * this.rate;
    this.position = Math.min(this.anchor.position + elapsed, segment.mark.start + segment.mark.length);
  }

  private positionOf(index: number, offset: number): number {
    return (this.segments[index]?.mark.start ?? 0) + offset / CHARS_PER_SECOND;
  }

  /** The character a position reaches inside a known part, moved back to its word's start. */
  private offsetIn(index: number, position: number): number {
    const segment = this.segments[index];
    if (!segment) return 0;
    const chars = Math.floor((position - segment.mark.start) * CHARS_PER_SECOND + EPSILON);
    return wordStart(segment.text, chars);
  }

  /** The part and word a position on the timeline falls in. The pause after a part belongs to the next one. */
  private locate(position: number): { index: number; offset: number } {
    let index = 0;
    this.segments.forEach((s, i) => {
      if (s.mark.start <= position + EPSILON) index = i;
    });
    const segment = this.segments[index];
    if (!segment) return { index: 0, offset: 0 };
    const chars = Math.floor((position - segment.mark.start) * CHARS_PER_SECOND + EPSILON);
    if (chars >= segment.text.length && index + 1 < this.segments.length)
      return { index: index + 1, offset: 0 };
    return { index, offset: wordStart(segment.text, chars) };
  }

  private makeState(): ListenState {
    return {
      playing: this.playing,
      position: this.position,
      total: this.timeline.total,
      currentPart: this.segments[this.index]?.mark.part ?? null,
      rate: this.rate,
      error: this.error,
    };
  }

  private emit(): void {
    if (this.disposed) return;
    this.snapshot = this.makeState();
    for (const listener of this.listeners) listener(this.snapshot);
  }
}

// ---------------------------------------------------------------------------------------------------------
// Offline (C-LISTEN.behaviour/4, L-LISTEN/5). Only the masked script is kept, with the time it was saved.

export interface ListenStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

const OFFLINE_PREFIX = "listen:";
const DAY_MS = 86_400_000;

type OfflineEntry = { savedAt: number; script: ListenScript };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isPart(value: unknown): value is ListenPart {
  return (
    isRecord(value) &&
    PART_IDS.some((id) => id === value.part) &&
    typeof value.title === "string" &&
    typeof value.text === "string"
  );
}

/** Copies only the fields a part has, so nothing else the caller's object carries is ever stored. */
function cleanScript(parts: readonly ListenPart[]): ListenScript {
  return { parts: parts.map(({ part, title, text }) => ({ part, title, text })) };
}

function readEntry(raw: string): OfflineEntry | null {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(value) || typeof value.savedAt !== "number" || !isRecord(value.script)) return null;
  const parts: unknown = value.script.parts;
  if (!Array.isArray(parts) || !parts.every(isPart)) return null;
  return { savedAt: value.savedAt, script: cleanScript(parts) };
}

/** True when the script was stored; false when the browser refused (private window, full, blocked). */
export function saveOffline(
  ideaId: string,
  script: ListenScript,
  storage: ListenStorage,
  now: number = Date.now(),
): boolean {
  const entry: OfflineEntry = { savedAt: now, script: cleanScript(script.parts) };
  try {
    storage.setItem(OFFLINE_PREFIX + ideaId, JSON.stringify(entry));
    return true;
  } catch {
    return false;
  }
}

/** The saved script, or null. An entry older than 30 days, or unreadable, is removed and reads as absent. */
export function loadOffline(
  ideaId: string,
  storage: ListenStorage,
  now: number = Date.now(),
): ListenScript | null {
  let raw: string | null;
  try {
    raw = storage.getItem(OFFLINE_PREFIX + ideaId);
  } catch {
    return null;
  }
  if (raw === null) return null;
  const entry = readEntry(raw);
  // Measured both ways, so a save stamped far in the future by a wrong device clock still runs out.
  if (entry && Math.abs(now - entry.savedAt) <= OFFLINE_DAYS * DAY_MS) return entry.script;
  forgetOffline(ideaId, storage);
  return null;
}

/** Called when the idea is decided, or when the reviewer removes the saved copy. */
export function forgetOffline(ideaId: string, storage: ListenStorage): void {
  try {
    storage.removeItem(OFFLINE_PREFIX + ideaId);
  } catch {
    // Storage is blocked; there is nothing to remove.
  }
}

/** Removes every saved script past 30 days, including ones for ideas the reviewer never opens again. */
export function pruneOffline(
  storage: ListenStorage & { readonly length: number; key(index: number): string | null },
  now: number = Date.now(),
): void {
  const ids: string[] = [];
  try {
    for (let i = 0; i < storage.length; i += 1) {
      const key = storage.key(i);
      if (key?.startsWith(OFFLINE_PREFIX)) ids.push(key.slice(OFFLINE_PREFIX.length));
    }
  } catch {
    return;
  }
  for (const id of ids) loadOffline(id, storage, now);
}
