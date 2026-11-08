/**
 * The scan as the submitter sees it (§4.2 steps 3–4, B4): status and step for the waiting screen, and the
 * person's choices when the scan stops — edit a blocked idea, say it is not personal data (it goes through,
 * flagged for the reviewer), take a redirect, or say "No, this is an idea" with a reason.
 * The worker restores tagged values; this module only decides who may see them (§3.1: the owner sees real
 * values of their own idea) and records choices.
 */
import { sql, type Transaction } from "kysely";

import { personalData, blocks } from "@/lib/canvas/rules";
import { emptyCanvas } from "@/lib/canvas/model";

import type { CurrentUser } from "./auth/current";
import { kfinDomains } from "./canvas-config";
import { encryptJson } from "./crypto";
import { getDb } from "./db";
import type { DB } from "./db-types";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

export type ScanChoice = "edit" | "not_personal_data" | "take_redirect" | "is_an_idea";
const CHOICES: readonly ScanChoice[] = ["edit", "not_personal_data", "take_redirect", "is_an_idea"];

async function ownedSubmitted(me: CurrentUser, id: string) {
  if (!/^[0-9a-f-]{36}$/.test(id) || !me.contributorCode) throw new SubmissionError(404, "not_found");
  const row = await getDb()
    .selectFrom("ideas")
    .select(["id", "idea_id", "stage", "contributor_code", "raw_encrypted"])
    .where("id", "=", id)
    .executeTakeFirst();
  if (!row || row.contributor_code !== me.contributorCode) throw new SubmissionError(404, "not_found");
  if (row.stage === "draft") throw new SubmissionError(409, "not_submitted");
  return row;
}

export async function scanStatus(me: CurrentUser, id: string) {
  await ownedSubmitted(me, id);
  const res = await workerFetch(`/internal/scans/${encodeURIComponent(id)}/view?mode=real`);
  if (res.status === 404) throw new SubmissionError(404, "not_found");
  if (!res.ok) throw new SubmissionError(502, "scan_unavailable");
  return (await res.json()) as Record<string, unknown>;
}

async function requeue(trx: Transaction<DB>, id: string) {
  await trx
    .updateTable("scans")
    .set({ state: "queued", step: "queued", outcome: null, finished_at: null })
    .where("idea_uuid", "=", id)
    .execute();
  await trx
    .insertInto("jobs")
    .values({
      type: "scan.run",
      payload: JSON.stringify({ idea_uuid: id }),
      dedupe_key: `scan:${id}:${Date.now()}`,
    })
    .execute();
}

export async function scanChoice(me: CurrentUser, id: string, input: unknown) {
  const row = await ownedSubmitted(me, id);
  const body = (input ?? {}) as { choice?: unknown; reason?: unknown };
  const choice = CHOICES.find((c) => c === body.choice);
  if (!choice) throw new SubmissionError(400, "choice_required");
  const scan = await getDb()
    .selectFrom("scans")
    .select(["outcome", "state", "overrides"])
    .where("idea_uuid", "=", id)
    .executeTakeFirst();
  const outcome = scan?.outcome ?? null;
  const needs: Record<ScanChoice, string> = {
    edit: "blocked",
    not_personal_data: "blocked",
    take_redirect: "redirect",
    is_an_idea: "redirect",
  };
  if (outcome !== needs[choice] || scan?.state !== "done")
    throw new SubmissionError(409, "not_available_now");
  const overrides = { ...((scan.overrides as Record<string, unknown>) ?? {}) };

  return getDb()
    .transaction()
    .execute(async (trx) => {
      if (choice === "edit") {
        // Back to a draft with the same IDs; the scan starts again on the next submit.
        await trx
          .updateTable("ideas")
          .set({
            stage: "draft",
            draft_encrypted: row.raw_encrypted, // same row-bound encryption context
            raw_encrypted: null,
            draft_expires_at: sql<Date>`now() + interval '30 days'`,
          })
          .where("id", "=", id)
          .where("stage", "=", "blocked")
          .execute();
        await trx.deleteFrom("scans").where("idea_uuid", "=", id).execute();
        return { next: `/share/${id}` };
      }
      if (choice === "take_redirect") {
        await trx.updateTable("ideas").set({ stage: "redirected" }).where("id", "=", id).execute();
        await trx.updateTable("scans").set({ outcome: "redirected" }).where("idea_uuid", "=", id).execute();
        return { next: null };
      }
      if (choice === "not_personal_data") {
        overrides.not_personal_data = true; // goes through, flagged for the reviewer (§4.2 step 3)
        await trx.updateTable("ideas").set({ stage: "scanning" }).where("id", "=", id).execute();
        await trx
          .updateTable("scans")
          .set({ overrides: JSON.stringify(overrides) })
          .where("idea_uuid", "=", id)
          .execute();
        await requeue(trx, id);
        return { next: null };
      }
      // is_an_idea: a reason of at least 15 characters, checked for personal data like any canvas text.
      const reason = typeof body.reason === "string" ? body.reason.trim().slice(0, 1000) : "";
      if (reason.length < 15) throw new SubmissionError(422, "reason_too_short");
      const probe = { ...emptyCanvas("full"), details: reason };
      if (blocks(personalData(probe, kfinDomains()).filter((h) => h.field === "details")))
        throw new SubmissionError(422, "personal_data");
      overrides.is_an_idea = true;
      await trx
        .updateTable("scans")
        .set({
          overrides: JSON.stringify(overrides),
          override_reason_encrypted: encryptJson({ reason }, `override:${id}`),
        })
        .where("idea_uuid", "=", id)
        .execute();
      await requeue(trx, id);
      return { next: null };
    });
}

export function isChoice(v: unknown): v is ScanChoice {
  return typeof v === "string" && (CHOICES as readonly string[]).includes(v);
}
