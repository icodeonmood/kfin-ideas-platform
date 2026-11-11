/**
 * Voice notes in quick capture (DEC-096): the recorder's plain words and pure helpers, kept apart from the
 * component so they can be unit-tested without a browser.
 */
import { BANNERS } from "@/lib/killswitch-routes";

export const MAX_SECONDS = 180;
export const AUDIO_BITS_PER_SECOND = 32_000; // about 0.7 MB for 3 minutes; speech needs no more
export const POLL_MS = 2000;

export const VOICE_TITLE = "Or record a voice note";
export const VOICE_START = "Record a voice note instead";
export const VOICE_NEW = "Voice notes are new. We're working to make them clearer, in more Indian languages.";
/** The one source of the paused-feature wording is BANNERS (BLD-157). */
export const VOICE_COMING_SOON = BANNERS["capture.voice"];
export const VOICE_HOW =
  "Speak in any language, for up to 3 minutes. We turn it into text in the box above for you to check. Nobody else hears it, and we delete the recording once it is text.";
export const VOICE_UNSUPPORTED = "Voice notes don't work in this browser. Please type it instead.";
export const VOICE_DONE = "Your words are in the box above. Check them and change anything we got wrong.";

/** The first recording format this browser supports; "" lets the browser choose. */
export function pickMimeType(isTypeSupported: (type: string) => boolean): string {
  for (const type of ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4", "audio/webm"]) {
    if (isTypeSupported(type)) return type;
  }
  return "";
}

/** "0:05", "2:59". */
export function formatElapsed(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function spoken(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  const parts = [m ? `${m} minute${m === 1 ? "" : "s"}` : "", s ? `${s} seconds` : ""].filter(Boolean);
  return parts.join(" ") || "0 seconds";
}

/**
 * What the live region says at this second, or null to stay quiet. Announcing every second would drown a
 * screen reader, so it speaks at the start, every 30 seconds, 10 seconds before the end and at the end.
 */
export function announcement(seconds: number, max = MAX_SECONDS): string | null {
  if (seconds === 0) return `Recording. You have up to ${spoken(max)}.`;
  if (seconds >= max) return `Recording stopped at ${spoken(max)}, the longest a voice note can be.`;
  if (seconds === max - 10) return "10 seconds left.";
  if (seconds % 30 === 0) return `Recording, ${spoken(seconds)}.`;
  return null;
}

/** The person's own words go after anything already in the box, never over it. */
export function insertTranscript(details: string, transcript: string): string {
  const text = transcript.trim();
  if (!text) return details;
  return details.trim() ? `${details.trimEnd()}\n\n${text}` : text;
}

export function leftOutMessage(count: number): string | null {
  if (!count) return null;
  return count === 1
    ? "We left out 1 detail that looked like investor or customer data."
    : `We left out ${count} details that looked like investor or customer data.`;
}

/** Plain words for an upload refusal or a failed transcription. Codes never reach the screen. */
export function failureMessage(code: string): string {
  switch (code) {
    case "voice_paused":
      return "Voice notes are paused just now. Please type it instead.";
    case "file_too_large":
      return "That recording is too long. Please keep it under 3 minutes.";
    case "too_long":
      return "That recording is longer than 3 minutes. Please record a shorter one.";
    case "type_not_allowed":
    case "codec_not_allowed":
    case "unreadable":
      return "We couldn't read that recording. Please try again, or type it instead.";
    case "deleted_by_person":
      return "Your voice note is deleted.";
    case "too_many_this_hour":
      return "You've sent several voice notes in the last hour. Please wait a little, or type it instead.";
    case "too_many_waiting":
      return "Please wait for your last voice note to turn into text before you send another.";
    case "virus":
      return "That recording didn't pass our safety check, so we deleted it. Please record it again.";
    case "nothing_heard":
      return "We couldn't hear any words in that recording. Please try again closer to the mic.";
    case "microphone_blocked":
      return "We couldn't use your microphone. Check your browser's permission for this site, or type it instead.";
    default:
      return "We couldn't turn that into text just now. Please try again, or type it instead.";
  }
}
