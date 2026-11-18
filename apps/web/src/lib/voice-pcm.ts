/**
 * The audio half of "By voice" in the browser (L-DRAFT.voice, BLD-C112, BLD-C118): what the AudioWorklet hears is
 * downsampled to 16 kHz mono, turned into 16-bit little-endian PCM and cut into one-second chunks numbered from 0.
 * Pure functions with no browser APIs, so the numbers can be tested exactly. Nothing here keeps audio: each chunk
 * leaves as soon as it is full, and the capture drops it once the worker has answered.
 */
import { VOICE_MAX_CHUNK_BYTES, VOICE_SAMPLE_RATE } from "./voice-stream";

/** Bytes in one second of 16 kHz mono 16-bit PCM: one chunk (the worker's contract, `chunk_seconds: 1`). */
export const VOICE_BYTES_PER_SECOND = VOICE_SAMPLE_RATE * 2;
export const VOICE_CHUNK_BYTES = VOICE_BYTES_PER_SECOND;
if (VOICE_CHUNK_BYTES > VOICE_MAX_CHUNK_BYTES) throw new Error("voice chunk larger than the worker accepts");

/**
 * Streaming downsampler from the AudioContext's rate (44.1 or 48 kHz) to 16 kHz. Each output sample is the mean of
 * the input samples in its window, `[floor(k·in/out), floor((k+1)·in/out))`, counted from the first sample pushed,
 * so blocks of any size give the same output as one long block and no drift builds up over three minutes.
 */
export class Downsampler {
  private buffer = new Float32Array(0);
  private base = 0; // absolute index of buffer[0] in the input
  private next = 0; // absolute index of the next output sample

  constructor(
    readonly inputRate: number,
    readonly outputRate: number = VOICE_SAMPLE_RATE,
  ) {
    if (!Number.isInteger(inputRate) || !Number.isInteger(outputRate) || outputRate <= 0)
      throw new RangeError("sample rates must be whole numbers");
    if (inputRate < outputRate) throw new RangeError("input rate below the output rate");
  }

  push(input: Float32Array): Float32Array {
    const joined = new Float32Array(this.buffer.length + input.length);
    joined.set(this.buffer);
    joined.set(input, this.buffer.length);
    const end = this.base + joined.length;
    const out: number[] = [];
    for (;;) {
      const from = Math.floor((this.next * this.inputRate) / this.outputRate);
      const to = Math.floor(((this.next + 1) * this.inputRate) / this.outputRate);
      if (to > end) break;
      let sum = 0;
      for (let i = from; i < to; i++) sum += joined[i - this.base] ?? 0;
      out.push(sum / (to - from));
      this.next += 1;
    }
    const keepFrom = Math.floor((this.next * this.inputRate) / this.outputRate);
    this.buffer = joined.slice(keepFrom - this.base);
    this.base = keepFrom;
    return Float32Array.from(out);
  }
}

/** Float samples in [-1, 1] to signed 16-bit little-endian PCM bytes (clamped; written with a DataView, so the
 * byte order never depends on the device). */
export function toPcm16le(samples: Float32Array): Uint8Array<ArrayBuffer> {
  const bytes = new Uint8Array(samples.length * 2);
  const view = new DataView(bytes.buffer);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i] ?? 0));
    const v = Math.round(s < 0 ? s * 0x8000 : s * 0x7fff);
    view.setInt16(i * 2, Math.max(-0x8000, Math.min(0x7fff, v)), true);
  }
  return bytes;
}

export type PcmChunk = { seq: number; data: Uint8Array<ArrayBuffer> };

/** Cuts the PCM byte stream into chunks of `size` bytes (one second), numbered from 0 in the order they are cut. */
export class PcmChunker {
  private pending = new Uint8Array(0);
  private seq = 0;

  constructor(readonly size: number = VOICE_CHUNK_BYTES) {
    if (size <= 0 || size % 2 || size > VOICE_MAX_CHUNK_BYTES) throw new RangeError("bad chunk size");
  }

  /** Every full chunk the new bytes complete. */
  push(bytes: Uint8Array): PcmChunk[] {
    const joined = new Uint8Array(this.pending.length + bytes.length);
    joined.set(this.pending);
    joined.set(bytes, this.pending.length);
    const out: PcmChunk[] = [];
    let at = 0;
    while (joined.length - at >= this.size) {
      out.push({ seq: this.seq++, data: joined.slice(at, at + this.size) });
      at += this.size;
    }
    this.pending = joined.slice(at);
    return out;
  }

  /** Numbers the next chunk `seq`: after the worker says where it is (a 409 chunk_out_of_order, BLD-C127). */
  continueFrom(seq: number): void {
    if (Number.isInteger(seq) && seq >= 0) this.seq = seq;
  }

  /** The last, shorter chunk when the note ends, or null if nothing is left. */
  flush(): PcmChunk | null {
    const rest = this.pending.length - (this.pending.length % 2); // whole samples only
    const data = this.pending.slice(0, rest);
    this.pending = new Uint8Array(0);
    return rest > 0 ? { seq: this.seq++, data } : null;
  }
}
