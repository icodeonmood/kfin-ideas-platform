/**
 * L-DRAFT.voice, BLD-C118: the audio half of "By voice" in the browser. The downsampler (48 and 44.1 kHz to
 * 16 kHz: lengths and values), 16-bit little-endian PCM, the one-second chunker (sizes, seq numbering) and the
 * AudioWorklet's mono mix-down, run from the exact source the page loads. Synthetic samples only.
 */
import { describe, expect, it } from "vitest";

import {
  Downsampler,
  PcmChunker,
  toPcm16le,
  VOICE_BYTES_PER_SECOND,
  VOICE_CHUNK_BYTES,
} from "@/lib/voice-pcm";
import { VOICE_MAX_CHUNK_BYTES, VOICE_SAMPLE_RATE } from "@/lib/voice-stream";
import { VOICE_WORKLET_BLOCK, VOICE_WORKLET_NAME, VOICE_WORKLET_SOURCE } from "@/lib/voice-worklet";

const ramp = (n: number) => Float32Array.from({ length: n }, (_, i) => ((i % 300) - 150) / 150);

describe("L-DRAFT.voice downsampler (BLD-C118)", () => {
  it("L-DRAFT.voice: one second at 48 kHz becomes 16,000 samples, each the mean of its three inputs", () => {
    const input = ramp(48_000);
    const out = new Downsampler(48_000).push(input);
    expect(out.length).toBe(16_000);
    for (const k of [0, 1, 99, 7_777, 15_999]) {
      const mean = (input[3 * k]! + input[3 * k + 1]! + input[3 * k + 2]!) / 3;
      expect(out[k]).toBeCloseTo(mean, 6);
    }
  });

  it("L-DRAFT.voice: blocks of any size give the same samples as one block, with nothing lost at the joins", () => {
    const input = ramp(48_000 * 2 + 5);
    const whole = new Downsampler(48_000).push(input);
    const d = new Downsampler(48_000);
    const parts: number[] = [];
    let at = 0;
    for (const size of [128, 1, 1_000, 7, 1_024, 44_000, 3]) {
      parts.push(...d.push(input.subarray(at, at + size)));
      at += size;
    }
    parts.push(...d.push(input.subarray(at)));
    expect(parts.length).toBe(whole.length);
    expect(parts.length).toBe(32_001); // 96,005 inputs: 32,001 whole windows of three
    parts.forEach((v, i) => expect(v).toBeCloseTo(whole[i]!, 6));
  });

  it("L-DRAFT.voice: 44.1 kHz gives exactly 16,000 a second with no drift, and a level stays the level", () => {
    const d = new Downsampler(44_100);
    let total = 0;
    for (let s = 0; s < 10; s++) {
      const out = d.push(new Float32Array(44_100).fill(0.25));
      total += out.length;
      expect(out.every((v) => Math.abs(v - 0.25) < 1e-6)).toBe(true);
    }
    expect(total).toBe(160_000);
  });

  it("L-DRAFT.voice: 16 kHz passes through unchanged; a rate below 16 kHz is refused", () => {
    const input = ramp(500);
    expect(Array.from(new Downsampler(VOICE_SAMPLE_RATE).push(input))).toEqual(Array.from(input));
    expect(() => new Downsampler(8_000)).toThrow(RangeError);
  });
});

describe("L-DRAFT.voice PCM and chunks (BLD-C112, BLD-C118)", () => {
  it("L-DRAFT.voice: floats become signed 16-bit little-endian, clamped at full scale", () => {
    const bytes = toPcm16le(Float32Array.from([0, 1, -1, 0.5, -0.5, 2, -2]));
    const view = new DataView(bytes.buffer);
    const values = Array.from({ length: 7 }, (_, i) => view.getInt16(i * 2, true));
    expect(values).toEqual([0, 32_767, -32_768, 16_384, -16_384, 32_767, -32_768]);
    expect(Array.from(bytes.subarray(2, 6))).toEqual([0xff, 0x7f, 0x00, 0x80]); // low byte first
  });

  it("L-DRAFT.voice: a chunk is one second (32,000 bytes), under the worker's limit", () => {
    expect(VOICE_CHUNK_BYTES).toBe(32_000);
    expect(VOICE_BYTES_PER_SECOND).toBe(32_000);
    expect(VOICE_CHUNK_BYTES).toBeLessThanOrEqual(VOICE_MAX_CHUNK_BYTES);
  });

  it("L-DRAFT.voice: the chunker cuts full seconds numbered from 0, then the rest on flush, losing no byte", () => {
    const c = new PcmChunker();
    const input = Uint8Array.from({ length: 32_000 * 2 + 16_000 }, (_, i) => i % 251);
    const chunks = [
      ...c.push(input.subarray(0, 10_000)),
      ...c.push(input.subarray(10_000, 50_000)),
      ...c.push(input.subarray(50_000)),
    ];
    expect(chunks.map((ch) => [ch.seq, ch.data.length])).toEqual([
      [0, 32_000],
      [1, 32_000],
    ]);
    const last = c.flush();
    expect(last?.seq).toBe(2);
    expect(last?.data.length).toBe(16_000);
    expect(c.flush()).toBeNull();
    const joined = new Uint8Array(input.length);
    let at = 0;
    for (const ch of [...chunks, last!]) {
      joined.set(ch.data, at);
      at += ch.data.length;
    }
    expect(Array.from(joined)).toEqual(Array.from(input));
  });

  it("L-DRAFT.voice: a stray odd byte is never sent (16-bit samples come in pairs)", () => {
    const c = new PcmChunker();
    c.push(new Uint8Array(5));
    expect(c.flush()?.data.length).toBe(4);
  });
});

describe("L-DRAFT.voice AudioWorklet source (BLD-C118)", () => {
  function load() {
    const posted: Float32Array[] = [];
    let registered: { name: string; ctor: new () => { process: (i: Float32Array[][]) => boolean } } | null = null;
    class AudioWorkletProcessor {
      port = { postMessage: (data: Float32Array) => posted.push(data.slice()) };
    }
    const registerProcessor = (name: string, ctor: never) => {
      registered = { name, ctor };
    };
    new Function("AudioWorkletProcessor", "registerProcessor", VOICE_WORKLET_SOURCE)(
      AudioWorkletProcessor,
      registerProcessor,
    );
    return { posted, registered: registered! as NonNullable<typeof registered> };
  }

  it("L-DRAFT.voice: registers under its name, mixes stereo to mono and posts blocks of 1,024 frames", () => {
    const { posted, registered } = load();
    expect(registered.name).toBe(VOICE_WORKLET_NAME);
    const proc = new registered.ctor();
    for (let q = 0; q < 9; q++) {
      const left = new Float32Array(128).fill(0.5);
      const right = new Float32Array(128).fill(-0.1);
      expect(proc.process([[left, right]])).toBe(true);
    }
    expect(posted.length).toBe(1); // 9 × 128 = 1,152 frames: one full block, 128 waiting
    expect(posted[0]!.length).toBe(VOICE_WORKLET_BLOCK);
    expect(posted[0]!.every((v) => Math.abs(v - 0.2) < 1e-6)).toBe(true);
    expect(proc.process([])).toBe(true); // no input yet: stays alive
  });
});
