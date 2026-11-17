/**
 * Drafts "By voice" through the worker (DEC-108, BLD-C112), shared by the routes and the S-04 builder.
 *
 * The browser sends raw little-endian 16-bit mono PCM at 16 kHz, about one second (32,000 bytes) per chunk, numbered
 * from 0 (`?stream=<id>&seq=<n>`). Sarvam's streaming API takes only WAV or PCM, so capture with an AudioWorklet and
 * downsample to 16 kHz; MediaRecorder's WebM/Opus is not accepted. Each chunk's answer carries the words heard so
 * far (`text`, with `spans` for the customer details found), for the person alone; `GET …/voice/:stream` polls.
 */
export const VOICE_SAMPLE_RATE = 16_000;
export const VOICE_MAX_CHUNK_BYTES = 64_000; // two seconds: room for a late timeslice; the worker refuses more
export const VOICE_MAX_SECONDS = 180; // L-DRAFT.voice/1

/** Shown before the person records (DEC-108 (5)): no vendor name (DEC-096). HR signs off the wording. */
export const VOICE_NOTICE =
  "Your voice note goes to an Indian speech service to turn it into text. You can check the text before you send it.";

/** The English copy's label (L-DRAFT.voice/4, the Ways board: "Typed up in English"). */
export const VOICE_EN_LABEL = "Typed up in English";

export type VoiceSpan = { start: number; end: number; kind: string };

export type VoiceStreamView =
  | {
      id: string;
      state: "live";
      next_seq: number;
      seconds: number;
      text: string;
      spans: VoiceSpan[];
    }
  | {
      id: string;
      state: "done";
      seconds: number;
      ended_by: "person" | "idle" | "limit" | "replaced" | "paused";
      text: string;
      spans: VoiceSpan[];
      hidden_count: number;
      text_en: string | null;
      text_en_label: string;
      translated: boolean | null;
      translation_failure: string | null;
      lang: string | null;
      language: string | null;
      summary: string;
    }
  | { id: string; state: "handed" | "expired"; seconds: number }
  | { id: string; state: "failed"; failure: string; ended_by: string | null };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
export const isUuid = (v: unknown): v is string => typeof v === "string" && UUID.test(v);

/** `seq` from the query string: a whole number from 0, or undefined. */
export function parseSeq(value: string | null): number | undefined {
  if (value === null || !/^\d{1,6}$/.test(value)) return undefined;
  return Number(value);
}
