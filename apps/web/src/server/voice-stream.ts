/**
 * Drafts "By voice", web side (DEC-108, BLD-C112). The worker holds the stream to Sarvam and the key; the web app
 * checks the session and passes the person's contributor code, and the worker checks they own the draft and the
 * stream. The audio passes through as bytes and is never kept.
 */
import { isUuid } from "@/lib/voice-stream";

import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";
import { spansForBrowser } from "./drafts";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

async function ownedDraft(me: CurrentUser, ideaUuid: string): Promise<void> {
  if (!isUuid(ideaUuid) || !me.contributorCode) throw new SubmissionError(404, "not_found");
  const idea = await getDb()
    .selectFrom("ideas")
    .select(["status", "contributor_code"])
    .where("id", "=", ideaUuid)
    .executeTakeFirst();
  // Someone else's draft looks exactly like a missing one.
  if (!idea || idea.contributor_code !== me.contributorCode) throw new SubmissionError(404, "not_found");
  if (idea.status !== "draft") throw new SubmissionError(409, "not_a_draft");
}

async function answer(res: Response): Promise<Record<string, unknown>> {
  const body = (await res.json().catch(() => ({ error: "voice_unavailable" }))) as Record<string, unknown>;
  if (!res.ok) {
    const { error, ...details } = body;
    throw new SubmissionError(res.status, String(error ?? "voice_unavailable"), spansForBrowser(details));
  }
  return spansForBrowser(body); // the words so far and the note: spans in UTF-16 units, as the browser draws them
}

function code(me: CurrentUser): string {
  if (!me.contributorCode) throw new SubmissionError(404, "not_found");
  return me.contributorCode;
}

export async function startVoice(me: CurrentUser, ideaUuid: string) {
  await ownedDraft(me, ideaUuid);
  const res = await workerFetch("/internal/voice-streams", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idea_uuid: ideaUuid, by_code: code(me), user_id: me.id }),
    signal: AbortSignal.timeout(30_000), // opening the stream to Sarvam, with its retries
  });
  return answer(res);
}

export async function sendChunk(
  me: CurrentUser,
  ideaUuid: string,
  stream: string,
  seq: number,
  data: ArrayBuffer,
) {
  if (!isUuid(ideaUuid) || !isUuid(stream)) throw new SubmissionError(404, "not_found");
  const q = new URLSearchParams({ idea_uuid: ideaUuid, by: code(me), seq: String(seq) });
  const res = await workerFetch(`/internal/voice-streams/${stream}/chunk?${q}`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: data,
    signal: AbortSignal.timeout(30_000), // the last chunk may end the note (flush and translation)
  });
  return answer(res);
}

export async function endVoice(me: CurrentUser, ideaUuid: string, stream: unknown) {
  if (!isUuid(ideaUuid) || !isUuid(stream)) throw new SubmissionError(404, "not_found");
  const res = await workerFetch(`/internal/voice-streams/${stream}/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idea_uuid: ideaUuid, by_code: code(me) }),
    signal: AbortSignal.timeout(60_000), // the last words after a flush, then the English copy
  });
  return answer(res);
}

export async function voiceStreamStatus(me: CurrentUser, ideaUuid: string, stream: string) {
  if (!isUuid(ideaUuid) || !isUuid(stream)) throw new SubmissionError(404, "not_found");
  const q = new URLSearchParams({ idea_uuid: ideaUuid, by: code(me) });
  return answer(await workerFetch(`/internal/voice-streams/${stream}?${q}`));
}
