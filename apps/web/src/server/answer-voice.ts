/**
 * S-R3's "Say your answer", web side (BLD-B276; DEC-108, L-QUESTIONS.answer/1): lane C's voice stream for an answer to
 * the review desk. The web app checks the session and passes the question's id, the person's id and their own
 * contributor code (`by`); the worker checks on every request that they are a sharer of the question's idea who may
 * answer it now, and that the stream is theirs (`desk.answer_voice`). Someone who may not answer gets 404, as with a
 * draft. The audio passes through as bytes and is never kept; nothing here logs words or audio.
 */
import { isUuid } from "@/lib/voice-stream";

import type { CurrentUser } from "./auth/current";
import { spansForBrowser } from "./drafts";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

async function answer(res: Response): Promise<Record<string, unknown>> {
  const body = (await res.json().catch(() => ({ error: "voice_unavailable" }))) as Record<string, unknown>;
  if (!res.ok) {
    const { error, ...details } = body;
    throw new SubmissionError(res.status, String(error ?? "voice_unavailable"), spansForBrowser(details));
  }
  return spansForBrowser(body); // the words so far and the note: spans in UTF-16 units, as the browser draws them
}

/** The question and the person, as the worker's routes take them; a bad id or no contributor code is not found. */
function who(me: CurrentUser, questionId: string): { question_id: string; user_id: string; by: string } {
  if (!isUuid(questionId) || !me.contributorCode) throw new SubmissionError(404, "not_found");
  return { question_id: questionId, user_id: me.id, by: me.contributorCode };
}

export async function startAnswerVoice(me: CurrentUser, questionId: string) {
  const res = await workerFetch("/internal/answer-voice-streams", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(who(me, questionId)),
    signal: AbortSignal.timeout(30_000), // opening the stream, with its retries
  });
  return answer(res);
}

export async function sendAnswerChunk(
  me: CurrentUser,
  questionId: string,
  stream: string,
  seq: number,
  data: ArrayBuffer,
) {
  const q = new URLSearchParams({ ...who(me, questionId), seq: String(seq) });
  if (!isUuid(stream)) throw new SubmissionError(404, "not_found");
  const res = await workerFetch(`/internal/answer-voice-streams/${stream}/chunk?${q}`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: data,
    signal: AbortSignal.timeout(30_000), // the last chunk may end the note
  });
  return answer(res);
}

export async function endAnswerVoice(me: CurrentUser, questionId: string, stream: unknown) {
  const body = who(me, questionId);
  if (!isUuid(stream)) throw new SubmissionError(404, "not_found");
  const res = await workerFetch(`/internal/answer-voice-streams/${stream}/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(60_000), // the last words after a flush
  });
  return answer(res);
}

export async function answerVoiceStatus(me: CurrentUser, questionId: string, stream: string) {
  const q = new URLSearchParams(who(me, questionId));
  if (!isUuid(stream)) throw new SubmissionError(404, "not_found");
  return answer(await workerFetch(`/internal/answer-voice-streams/${stream}?${q}`));
}
