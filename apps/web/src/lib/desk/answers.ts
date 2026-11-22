/**
 * S-R3's saves (L-QUESTIONS.answer, A-API.questions): each answer is saved as it is typed, and what the server holds
 * is what the screen reports. Framework-free, so the failure paths are tested without a browser.
 */
import type { AnswerFile } from "@/lib/contracts";
import { replyError } from "@/lib/desk/reply";
import { COUNTS_EVENT } from "@/lib/inbox-events";

/** V-FIELDS.answer/1: up to 2,000 characters, with a counter once the answer is near the limit. */
export const MAX_ANSWER = 2000;
export const NEAR_LIMIT = 1800;
/** F-COPY's failure line for a save that did not reach the server; the save is tried again on its own. */
export const SAVE_FAILED = "Couldn’t save that. Try again.";
export const RETRY_MS = 4000;
export const SAVE_AFTER_MS = 700;

/** A save that reached the server: the text it holds, and (BLD-B275) the answer's id and files when its reply has
 * them, so S-R3's "+" knows the answer row an upload goes to. */
export type SaveResult =
  | { ok: true; text: string; id?: string; files?: AnswerFile[] }
  | { ok: false; message: string; retry: boolean };

/** One answer to the server (A-API.questions `PUT /api/questions/:id/answer`). An empty text saves too: the first
 * save makes the answer's row (the worker's `save_answer`). Never throws. */
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
    const saved: Extract<SaveResult, { ok: true }> = { ok: true, text: body.text };
    if ("id" in body && typeof body.id === "string") saved.id = body.id;
    if ("files" in body && Array.isArray(body.files)) saved.files = body.files as AnswerFile[];
    return saved;
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

/** After the answers send: the item leaves "Needs you" (L-INBOX.rules/3), so every Inbox count is read again and
 * sent on the reader's COUNTS_EVENT, as the reader does when it opens or answers an item (V-ACC.track/8). The
 * sidebar shows unread, which sending does not change; its listener keeps it in step with the counts all the same.
 * Never throws; a count that cannot be read waits for the next page. */
export async function tellInboxCounts(): Promise<void> {
  try {
    const res = await fetch("/api/inbox/counts", { cache: "no-store" });
    if (!res.ok) return;
    const counts: unknown = await res.json();
    if (!counts || typeof counts !== "object" || typeof (counts as { unread?: unknown }).unread !== "number")
      return;
    window.dispatchEvent(new CustomEvent(COUNTS_EVENT, { detail: counts }));
  } catch {
    return;
  }
}
