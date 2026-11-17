/**
 * S-R3's saves (L-QUESTIONS.answer, A-API.questions): each answer is saved as it is typed, and what the server holds
 * is what the screen reports. Framework-free, so the failure paths are tested without a browser.
 */
import { replyError } from "@/lib/desk/reply";

/** V-FIELDS.answer/1: up to 2,000 characters, with a counter once the answer is near the limit. */
export const MAX_ANSWER = 2000;
export const NEAR_LIMIT = 1800;
/** F-COPY's failure line for a save that did not reach the server; the save is tried again on its own. */
export const SAVE_FAILED = "Couldn’t save that. Try again.";
export const RETRY_MS = 4000;
export const SAVE_AFTER_MS = 700;

export type SaveResult = { ok: true; text: string } | { ok: false; message: string; retry: boolean };

/** One answer to the server (A-API.questions `PUT /api/questions/:id/answer`). Never throws. */
export async function putAnswer(questionId: string, text: string): Promise<SaveResult> {
  let res: Response;
  try {
    res = await fetch(`/api/questions/${encodeURIComponent(questionId)}/answer`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  } catch {
    return { ok: false, message: SAVE_FAILED, retry: true };
  }
  const body: unknown = await res.json().catch(() => null);
  if (res.ok && body && typeof body === "object" && "text" in body && typeof body.text === "string") {
    return { ok: true, text: body.text };
  }
  // The worker's own refusal ("Keep your answer under 2,000 characters.") is shown as it is and not tried again;
  // a paused feature shows its banner; anything else is the failure line, tried again.
  const e = replyError(body);
  const worker = res.status === 422 || res.status === 409;
  return {
    ok: false,
    message: worker || res.status === 503 ? (e?.message ?? SAVE_FAILED) : SAVE_FAILED,
    retry: !worker,
  };
}
