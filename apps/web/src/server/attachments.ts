/**
 * Research attachments, web side (§4.2 "Attachments", AT-B3-06/07). Files go straight to the worker, which
 * stores them in quarantine and checks them; the web app decides who may upload, see and open them.
 * Day one: a clean file opens for its owner and for the review desk, core committee and admins once the idea
 * is submitted (BLD-059). Anything not clean returns 403 to everyone. The 1% Club's files and answer files
 * (`file_state` or `answer_id` set) are not found here: they open only through `/api/files/:id/view`.
 */
import { can } from "@/lib/rbac";

import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

export type AttachmentView = {
  id: string;
  name: string;
  bytes: number;
  state: "quarantine" | "processing" | "awaiting_check" | "clean" | "rejected";
  rejection: { type: string; code?: string; location: string } | null;
};

export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024; // rules/thresholds.md; the worker enforces the rule's value too

export async function listFor(ideaUuid: string): Promise<AttachmentView[]> {
  const rows = await getDb()
    .selectFrom("attachments")
    .select(["id", "name", "bytes", "state", "rejection"])
    .where("idea_uuid", "=", ideaUuid)
    .orderBy("created_at")
    .execute();
  return rows.map((r) => ({
    id: r.id,
    name: r.name,
    bytes: Number(r.bytes),
    state: r.state as AttachmentView["state"],
    rejection: (r.rejection as AttachmentView["rejection"]) ?? null,
  }));
}

async function ownedDraft(me: CurrentUser, ideaUuid: string) {
  if (!/^[0-9a-f-]{36}$/.test(ideaUuid)) throw new SubmissionError(404, "not_found");
  const idea = await getDb()
    .selectFrom("ideas")
    .select(["id", "stage", "contributor_code"])
    .where("id", "=", ideaUuid)
    .executeTakeFirst();
  if (!idea || idea.contributor_code !== me.contributorCode) throw new SubmissionError(404, "not_found");
  if (idea.stage !== "draft") throw new SubmissionError(409, "not_a_draft");
  return idea;
}

export async function upload(me: CurrentUser, ideaUuid: string, file: File) {
  await ownedDraft(me, ideaUuid);
  const form = new FormData();
  form.set("idea_uuid", ideaUuid);
  form.set("uploaded_by_code", me.contributorCode!);
  form.set("file", file, file.name.slice(0, 200));
  const res = await workerFetch("/internal/attachments", {
    method: "POST",
    body: form,
    signal: AbortSignal.timeout(60_000),
  });
  const body = (await res.json().catch(() => ({ error: "upload_failed" }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(body.error ?? "upload_failed"));
  return body;
}

export async function remove(me: CurrentUser, ideaUuid: string, attId: string) {
  await ownedDraft(me, ideaUuid);
  const att = await getDb()
    .selectFrom("attachments")
    .select("id")
    .where("id", "=", attId)
    .where("idea_uuid", "=", ideaUuid)
    .executeTakeFirst();
  if (!att) throw new SubmissionError(404, "not_found");
  const res = await workerFetch(`/internal/attachments/${encodeURIComponent(attId)}`, { method: "DELETE" });
  if (!res.ok) throw new SubmissionError(502, "delete_failed");
}

/** Who may see a file's status or open it: the owner, or the review roles once the idea is submitted. */
export async function accessible(me: CurrentUser, attId: string) {
  if (!/^ATT-[0-9]{4}-[0-9]{6}$/.test(attId)) return null;
  const row = await getDb()
    .selectFrom("attachments as a")
    .innerJoin("ideas as i", "i.id", "a.idea_uuid")
    .select([
      "a.id",
      "a.name",
      "a.bytes",
      "a.state",
      "a.rejection",
      "a.mime",
      "a.file_state",
      "a.answer_id",
      "i.contributor_code",
      "i.stage",
    ])
    .where("a.id", "=", attId)
    .executeTakeFirst();
  if (!row) return null;
  // A 1% Club file or link, or any file on an answer, belongs to the files pipeline (A-API.files): it opens only
  // through /api/files/:id/view under DEC-107's rule, never through this older route, whatever its state.
  if (row.file_state !== null || row.answer_id !== null) return null;
  const owner = row.contributor_code === me.contributorCode;
  const reviewer = can(me.roles, "view_review_queue") && row.stage !== "draft";
  return owner || reviewer ? row : null;
}
