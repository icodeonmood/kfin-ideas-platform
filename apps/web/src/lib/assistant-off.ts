/**
 * DEC-143 (f), BLD-B282: a text that must pass the checks before it is stored (the Showcase brief, the Ember note,
 * delivery's notes) still cannot be saved while the assistant is off, since nothing unchecked is stored (non-negotiable
 * 4). The refusal now says so and that it saves once the assistant is back; the form keeps the words as typed.
 * Client-safe: no server imports.
 */

/** The web app's code for a text check that did not run because the assistant is off (`server/worker-codes.ts`). */
export const ASSISTANT_OFF = "assistant_off";

/** New words (DEC-143 (f)), listed under BUILD_LOG "To confirm later". */
export const SAVES_ONCE_BACK =
  "The assistant is taking a break, so this can’t be saved yet. Your words are still here. Save again once it’s back.";
