/**
 * S-R3's "Say your answer" (BLD-B276; C-PROMPT.voice, L-QUESTIONS.answer/1; DEC-108, DEC-131(5)): lane C's voice
 * capture, sent to the question's own routes (`/api/questions/{id}/answer/voice/*`). The words the person said go
 * into the answer box after what it holds, as typing would add them, and save with the box's autosave. No English
 * copy is made for an answer. Framework-free, so the joins are tested without a browser.
 */
import { BANNERS } from "@/lib/killswitch-routes";
import type { VoiceCaptureState } from "@/lib/voice-capture";

/** The mic's words in the answer box: its name and the box's placeholder are the boards' (reference/copy/Answer.md and
 * PhoneAnswer.md, word for word); a paused or signed-out note says what Share's box says (COMPOSE_COPY), from the same
 * sources, so S-R3 does not load Share's screen. A unit test keeps them the same. */
export const ANSWER_VOICE_COPY = {
  say: "Say your answer",
  placeholder: "Type your answer, or tap the mic and say it",
  paused: BANNERS["capture.voice"],
  signInAgain: "Sign in again to carry on",
} as const;

/** Which line a failed note shows, as Share's `voiceFailedLine` says: sign in again, the voice-off line, or none (the
 * other reasons are codes with no copy; typing always works). */
export function voiceFailedLine(reason: string): "sign_in" | "paused" | null {
  if (reason === "signed_out") return "sign_in";
  if (["paused", "unavailable", "voice_paused", "voice_unavailable"].includes(reason)) return "paused";
  return null;
}

/** Where a question's note goes: `${base}/start`, `/chunk`, `/end` and `/{stream}` (lane C's `base` option). */
export function answerVoiceBase(questionId: string): string {
  return `/api/questions/${encodeURIComponent(questionId)}/answer/voice`;
}

/** A note is on its way: the browser is asking for the mic, the person is speaking, or the last words are coming. */
export function isSpeaking(status: VoiceCaptureState["status"]): boolean {
  return status === "asking" || status === "recording" || status === "sending";
}

/** The answer with the person's spoken words after it, one space between, as typing would add them. Nothing heard is
 * dropped: an answer that runs past the limit shows the counter, and the worker's own line says to shorten it. */
export function withSpoken(text: string, words: string): string {
  if (!words.trim()) return text;
  return text.trim() ? `${text.replace(/\s+$/, "")} ${words}` : words;
}

/** The words a finished, paused or failed note leaves for the box (a paused note's once the worker kept them), or
 * "" when there are none to take. */
export function spokenWords(state: VoiceCaptureState): string {
  if (state.status === "done") return state.note.text;
  if (state.status === "paused") return state.note?.text ?? "";
  if (state.status === "failed") return state.text;
  return "";
}
