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

async function requeue(trx: Transaction<DB>, id: string, attempts: number) {
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
      dedupe_key: `scan-requeue:${id}:${attempts}`, // a double click queues one scan, not two
    })
    .onConflict((oc) => oc.doNothing())
    .execute();
}

/**
 * The person's choice when a scan stops. One transaction with the scan row locked, so two clicks (or two
 * buttons) cannot both act; every change is guarded by the stage it expects (B4 review, BLD-081).
 */
export async function scanChoice(me: CurrentUser, id: string, input: unknown) {
  const row = await ownedSubmitted(me, id);
  const body = (input ?? {}) as { choice?: unknown; reason?: unknown };
  const choice = CHOICES.find((c) => c === body.choice);
  if (!choice) throw new SubmissionError(400, "choice_required");
  // What the person was shown: whether they may contest, and the reason length from rules/redirects.md.
  const view = (await scanStatus(me, id)) as {
    blocked?: { can_contest?: boolean; investor_context?: boolean };
    redirect?: { override_reason_min_chars?: number };
  };
  const needs: Record<ScanChoice, string> = {
    edit: "blocked",
    not_personal_data: "blocked",
    take_redirect: "redirect",
    is_an_idea: "redirect",
  };
  let reason = "";
  // Every gatekeeper block can be contested (BLD-082 option B); the worker still says so per scan.
  if (choice === "not_personal_data" && view.blocked?.can_contest !== true)
    throw new SubmissionError(409, "not_available_now");
  if (choice === "is_an_idea") {
    reason = typeof body.reason === "string" ? body.reason.trim().slice(0, 1000) : "";
    if (reason.length < (view.redirect?.override_reason_min_chars ?? 15))
      throw new SubmissionError(422, "reason_too_short");
    const probe = { ...emptyCanvas("full"), details: reason };
    if (blocks(personalData(probe, kfinDomains()).filter((h) => h.field === "details")))
      throw new SubmissionError(422, "personal_data");
  }

  return getDb()
    .transaction()
    .execute(async (trx) => {
      const scan = await trx
        .selectFrom("scans")
        .select(["outcome", "state", "overrides", "attempts"])
        .where("idea_uuid", "=", id)
        .forUpdate()
        .executeTakeFirst();
      if (!scan || scan.state !== "done" || scan.outcome !== needs[choice])
        throw new SubmissionError(409, "not_available_now");
      const overrides = { ...((scan.overrides as Record<string, unknown>) ?? {}) };
      const expect = (stage: string, n: bigint | number) => {
        if (Number(n) !== 1) throw new SubmissionError(409, "not_available_now");
        return stage;
      };

      if (choice === "edit") {
        // Back to a draft with the same IDs; values held for it are dropped and re-tagged on the next submit.
        const moved = await trx
          .updateTable("ideas")
          .set({
            stage: "draft",
            draft_encrypted: row.raw_encrypted, // same row-bound encryption context
            raw_encrypted: null,
            draft_expires_at: sql<Date>`now() + interval '30 days'`,
          })
          .where("id", "=", id)
          .where("stage", "=", "blocked")
          .executeTakeFirst();
        expect("blocked", moved.numUpdatedRows);
        await trx.deleteFrom("scans").where("idea_uuid", "=", id).execute();
        if (row.idea_id)
          await trx
            .insertInto("jobs")
            .values({
              type: "vault.purge_scope",
              payload: JSON.stringify({ scope_id: row.idea_id }),
              dedupe_key: `vault-purge:${row.idea_id}:${scan.attempts}`,
            })
            .onConflict((oc) => oc.doNothing())
            .execute();
        return { next: `/share/${id}` };
      }
      if (choice === "take_redirect") {
        const moved = await trx
          .updateTable("ideas")
          .set({ stage: "redirected" })
          .where("id", "=", id)
          .where("stage", "=", "scanning")
          .executeTakeFirst();
        expect("scanning", moved.numUpdatedRows);
        await trx.updateTable("scans").set({ outcome: "redirected" }).where("idea_uuid", "=", id).execute();
        return { next: null };
      }
      if (choice === "not_personal_data") {
        overrides.not_personal_data = true; // goes through, flagged for the reviewer (§4.2 step 3)
        const moved = await trx
          .updateTable("ideas")
          .set({ stage: "scanning" })
          .where("id", "=", id)
          .where("stage", "=", "blocked")
          .executeTakeFirst();
        expect("blocked", moved.numUpdatedRows);
        await trx
          .updateTable("scans")
          .set({ overrides: JSON.stringify(overrides) })
          .where("idea_uuid", "=", id)
          .execute();
        // IDs and a code only: never the flagged words (non-negotiable 3).
        await trx
          .insertInto("audit_log")
          .values({
            actor: `user:${me.id}`,
            action: "scan.contest",
            entity: `idea:${row.idea_id}`,
            after: JSON.stringify({ investor_or_customer: view.blocked?.investor_context === true }),
          })
          .execute();
        await requeue(trx, id, scan.attempts);
        return { next: null };
      }
      overrides.is_an_idea = true;
      await trx
        .updateTable("scans")
        .set({
          overrides: JSON.stringify(overrides),
          override_reason_encrypted: encryptJson({ reason }, `override:${id}`),
        })
        .where("idea_uuid", "=", id)
        .execute();
      await requeue(trx, id, scan.attempts);
      return { next: null };
    });
}

export function isChoice(v: unknown): v is ScanChoice {
  return typeof v === "string" && (CHOICES as readonly string[]).includes(v);
}

/** "Looks right": keep or clear each suggestion, and the owner's edits to the one line and details. */
export async function confirmCard(me: CurrentUser, id: string, input: unknown) {
  await ownedSubmitted(me, id);
  const body = (input ?? {}) as { one_line?: unknown; details?: unknown; keep?: unknown };
  const keep: Record<string, boolean> = {};
  if (body.keep && typeof body.keep === "object")
    for (const [k, v] of Object.entries(body.keep as Record<string, unknown>))
      if (/^[a-z_.]{1,60}$/.test(k) && typeof v === "boolean") keep[k] = v;
  const payload: Record<string, unknown> = { keep };
  if (typeof body.one_line === "string") payload.one_line = body.one_line.slice(0, 400);
  if (typeof body.details === "string") payload.details = body.details.slice(0, 10_000);
  const res = await workerFetch(`/internal/scans/${encodeURIComponent(id)}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(30_000),
  });
  const out = (await res.json().catch(() => ({ error: "confirm_failed" }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(out.error ?? "confirm_failed"), out.details);
  return out;
}

const SAVE_CHOICES = ["team_up", "plus_one", "different", "something_changed", "new", "withdraw"] as const;

/** Find your crew: the person's choice, saved in one transaction by the worker (§4.2 step 8). */
export async function chooseMatch(me: CurrentUser, id: string, input: unknown) {
  await ownedSubmitted(me, id);
  const body = (input ?? {}) as { choice?: unknown; ref?: unknown; text?: unknown };
  const choice = SAVE_CHOICES.find((c) => c === body.choice);
  if (!choice) throw new SubmissionError(400, "choice_required");
  const ref = typeof body.ref === "string" && /^m[0-9a-f]{10}$/.test(body.ref) ? body.ref : null;
  const text = typeof body.text === "string" ? body.text.slice(0, 1000) : "";
  const res = await workerFetch(`/internal/scans/${encodeURIComponent(id)}/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ choice, ref, text, contributor_code: me.contributorCode }),
    signal: AbortSignal.timeout(30_000),
  });
  const out = (await res.json().catch(() => ({ error: "save_failed" }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(out.error ?? "save_failed"));
  return out;
}
