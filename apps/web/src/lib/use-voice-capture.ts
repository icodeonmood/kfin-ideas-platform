"use client";
/**
 * `useVoiceCapture(draftId)`: "By voice" for C-PROMPT on S-04, with no look of its own (L-DRAFT.voice,
 * C-PROMPT.voice; BLD-C118). Lane D draws each state; this hook only says which one it is.
 *
 *   idle       mic button; `notice` (VOICE_NOTICE) is set until the person's first recording on this device
 *   asking     the browser is asking for the microphone
 *   blocked    `title` and `body`: C-PROMPT.voice "Blocked" for this device, word for word (role="alert")
 *   recording  "Listening. Up to 3 minutes." (VOICE_LISTENING); `seconds` counts up to `maxSeconds`; `text` and
 *              `spans` are the words so far, with the hidden details to underline
 *   sending    the last words are on their way, or the page is reading back a note after a lost connection
 *   done       `note.text` (their words, editable), `note.textEn` with `note.enLabel` ("Typed up in English"),
 *              `note.spans`; hand `note.streamId` to the draft, then `reset()`
 *   paused     voice was switched off: show `banner`, the kill switch's own words; `note` fills in if the words
 *              were kept
 *   failed     `reason` is a code (no copy is drawn for it); typing always works
 *
 * Call `start()` from the mic's click handler. The microphone is allowed on every app page, `microphone=(self)`
 * (next.config.ts, DEC-128).
 */
import { useEffect, useState, useSyncExternalStore } from "react";

import { VoiceCapture, type VoiceCaptureOptions, type VoiceCaptureState } from "./voice-capture";

const SERVER: VoiceCaptureState = { status: "idle", notice: null };
const server = () => SERVER;

export type UseVoiceCapture = {
  state: VoiceCaptureState;
  start: () => Promise<void>;
  stop: () => void;
  reset: () => void;
  /** Call once the notice is on screen; the first recording then marks it seen (BLD-C127). */
  noticeShown: () => void;
};

export function useVoiceCapture(draftId: string, options?: VoiceCaptureOptions): UseVoiceCapture {
  const [capture, setCapture] = useState(() => new VoiceCapture(draftId, options));
  if (capture.draftId !== draftId) setCapture(new VoiceCapture(draftId, options)); // a different draft
  useEffect(() => () => capture.dispose(), [capture]);
  const state = useSyncExternalStore(capture.subscribe, capture.getState, server);
  return {
    state,
    start: capture.start,
    stop: capture.stop,
    reset: capture.reset,
    noticeShown: capture.noticeShown,
  };
}
