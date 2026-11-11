/**
 * Voice notes in quick capture, web side (DEC-096). A recording goes straight to the worker, which keeps it in
 * quarantine, scans it, turns it into text and deletes it; the web app only checks that the person owns the draft.
 * The text comes back to its owner alone, once, and the browser then deletes the held copy.
 */
import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

export const MAX_VOICE_BYTES = 5 * 1024 * 1024; // the worker enforces the same limit

export type VoiceView = {
  id: string;
  state: "quarantine" | "transcribing" | "ready" | "failed" | "deleted";
  failure?: string;
  transcript?: string;
  removed_count?: number;
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

async function ownedDraft(me: CurrentUser, ideaUuid: string) {
  if (!UUID.test(ideaUuid)) throw new SubmissionError(404, "not_found");
  const idea = await getDb()
    .selectFrom("ideas")
    .select(["id", "stage", "contributor_code"])
    .where("id", "=", ideaUuid)
    .executeTakeFirst();
  // Someone else's draft looks exactly like a missing one.
  if (!idea || !me.contributorCode || idea.contributor_code !== me.contributorCode)
    throw new SubmissionError(404, "not_found");
  return idea;
}

export async function uploadVoice(me: CurrentUser, ideaUuid: string, file: Blob) {
  const idea = await ownedDraft(me, ideaUuid);
  if (idea.stage !== "draft") throw new SubmissionError(409, "not_a_draft");
  const form = new FormData();
  form.set("idea_uuid", ideaUuid);
  form.set("uploaded_by_code", me.contributorCode!);
  form.set("file", file, "voice-note"); // no file name is kept
  const res = await workerFetch("/internal/voice", {
    method: "POST",
    body: form,
    signal: AbortSignal.timeout(60_000),
  });
  const body = (await res.json().catch(() => ({ error: "upload_failed" }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(body.error ?? "upload_failed"));
  return body;
}

export async function voiceStatus(me: CurrentUser, ideaUuid: string, voiceId: string): Promise<VoiceView> {
  await ownedDraft(me, ideaUuid);
  if (!UUID.test(voiceId)) throw new SubmissionError(404, "not_found");
  const res = await workerFetch(
    `/internal/voice/${encodeURIComponent(voiceId)}?idea_uuid=${encodeURIComponent(ideaUuid)}`,
  );
  if (res.status === 404) throw new SubmissionError(404, "not_found");
  if (!res.ok) throw new SubmissionError(502, "status_failed");
  return (await res.json()) as VoiceView;
}

export async function removeVoice(me: CurrentUser, ideaUuid: string, voiceId: string) {
  await ownedDraft(me, ideaUuid);
  if (!UUID.test(voiceId)) throw new SubmissionError(404, "not_found");
  // The worker's audit names who deleted it, by contributor code only.
  const res = await workerFetch(
    `/internal/voice/${encodeURIComponent(voiceId)}?idea_uuid=${encodeURIComponent(ideaUuid)}` +
      `&by=${encodeURIComponent(me.contributorCode ?? "")}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new SubmissionError(502, "delete_failed");
}
