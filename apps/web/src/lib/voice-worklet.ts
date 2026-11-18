/**
 * The AudioWorklet for "By voice" (BLD-C118). It mixes the microphone down to mono and posts blocks of float
 * samples to the page, which downsamples them to 16 kHz PCM (`voice-pcm.ts`). It writes no output, so nothing is
 * played back, and it keeps nothing beyond the block it is filling.
 *
 * The source is loaded from a Blob URL rather than a file in `public/`: the page needs no extra route through the
 * proxy, and the bundle carries the exact code the tests run.
 */
export const VOICE_WORKLET_NAME = "kfin-voice-pcm";

/** Frames per message: 1,024 (about 21 ms at 48 kHz), so the page gets about 47 messages a second. */
export const VOICE_WORKLET_BLOCK = 1024;

export const VOICE_WORKLET_SOURCE = `
class VoicePcm extends AudioWorkletProcessor {
  constructor() {
    super();
    this.block = new Float32Array(${VOICE_WORKLET_BLOCK});
    this.filled = 0;
  }
  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const channels = input.length;
    const frames = input[0].length;
    for (let i = 0; i < frames; i++) {
      let sum = 0;
      for (let c = 0; c < channels; c++) sum += input[c][i];
      this.block[this.filled++] = sum / channels;
      if (this.filled === this.block.length) {
        this.port.postMessage(this.block, [this.block.buffer]);
        this.block = new Float32Array(${VOICE_WORKLET_BLOCK});
        this.filled = 0;
      }
    }
    return true;
  }
}
registerProcessor(${JSON.stringify(VOICE_WORKLET_NAME)}, VoicePcm);
`;

let url: string | null = null;

/** One Blob URL for the page's lifetime. */
export function voiceWorkletUrl(): string {
  url ??= URL.createObjectURL(new Blob([VOICE_WORKLET_SOURCE], { type: "text/javascript" }));
  return url;
}
