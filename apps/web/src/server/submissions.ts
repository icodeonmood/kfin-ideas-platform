/**
 * Drafts and submission (§4.1 steps 2 and 4; AT-B3-02/03/04/08).
 *
 * - A draft lives in `ideas` with stage `draft`; its answers are encrypted in `draft_encrypted` and it expires
 *   after the retention period (rules/thresholds.md `canvas.draft_retention_days`). Drafts never reach the repo.
 * - The server re-runs the personal-data check on every save and refuses to store a blocking match, even
 *   encrypted, so autosave cannot persist investor data that slipped past the browser.
 * - Submit validates, assigns SUB- and IDEA- IDs with the same number, stores the answers encrypted in
 *   `raw_encrypted` until the scan (B4) has tagged them, sets stage `scanning` and queues `scan.run`.
 *   Only enums and numbers go into plain columns.
 */
import { randomUUID } from "node:crypto";

import { sql } from "kysely";

import { emptyCanvas, type Canvas, type Mode } from "@/lib/canvas/model";
import { blocks, finaliseQuick, personalData, strength, validate, type FieldError } from "@/lib/canvas/rules";

import type { CurrentUser } from "./auth/current";
import { canvasConfig, kfinDomains } from "./canvas-config";
import { decryptJson, encryptJson } from "./crypto";
import { getDb } from "./db";

export class SubmissionError extends Error {
  constructor(
    public status: number,
    public code: string,
    public details?: unknown,
  ) {
    super(code);
  }
}

const IST = "Asia/Kolkata";

function owned(me: CurrentUser) {
  if (!me.contributorCode) throw new SubmissionError(409, "no_contributor_code");
  return me.contributorCode;
}

/** Canvas from untrusted JSON: start from an empty canvas and keep only known fields of the right type. */
export function sanitiseCanvas(input: unknown, mode: Mode): Canvas {
  const c = emptyCanvas(mode);
  if (!input || typeof input !== "object") return c;
  const src = input as Record<string, unknown>;
  const text = (v: unknown, max = 10_000) => (typeof v === "string" ? v.slice(0, max) : "");
  const pick = <T extends string>(v: unknown, allowed: readonly T[]) =>
    typeof v === "string" && (allowed as readonly string[]).includes(v) ? (v as T) : null;
  const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) && v >= 0 && v < 1e15 ? v : null);

  c.kind = pick(src.kind, ["problem", "problem_with_solution", "business_idea"] as const);
  c.one_line = text(src.one_line, 400);
  c.details = text(src.details);
  const who = (src.who ?? {}) as Record<string, unknown>;
  const segs = ["investors", "distributors", "amc_clients", "issuer_clients", "kfin_teams", "other"] as const;
  c.who.segments = Array.isArray(who.segments)
    ? [
        ...new Set(
          who.segments.map((s) => pick(s, segs)).filter((s): s is (typeof segs)[number] => s !== null),
        ),
      ]
    : [];
  c.who.frequency_or_reach = text(who.frequency_or_reach, 100);
  c.who.today_alternative = text(who.today_alternative, 2000);
  const value = (src.value ?? {}) as Record<string, unknown>;
  c.value.category = pick(value.category, ["cost_saving", "new_revenue", "both", "not_sure"] as const);
  c.value.play = pick(value.play, [
    "process_improvement",
    "upsell",
    "cross_sell",
    "new_product",
    "other",
  ] as const);
  c.value.basis = pick(value.basis, ["own_data", "document", "conversation", "hunch"] as const);
  const est = (value.estimate ?? {}) as Record<string, unknown>;
  c.value.estimate = {
    hours_saved_per_month: num(est.hours_saved_per_month),
    inr_saved_per_year: num(est.inr_saved_per_year),
    inr_revenue_one_time: num(est.inr_revenue_one_time),
    inr_revenue_per_year: num(est.inr_revenue_per_year),
    clients_who_would_pay: num(est.clients_who_would_pay),
    note: text(est.note, 400) || null,
  };
  const eco = (src.ecosystem ?? {}) as Record<string, unknown>;
  c.ecosystem.solved_elsewhere = pick(eco.solved_elsewhere, ["yes", "partly", "no", "dont_know"] as const);
  c.ecosystem.our_advantage = text(eco.our_advantage, 2000);
  const players = ["rta", "amc", "fintech", "bank", "global", "internal", "other"] as const;
  c.ecosystem.references = Array.isArray(eco.references)
    ? eco.references.slice(0, 20).flatMap((r) => {
        const ref = (r ?? {}) as Record<string, unknown>;
        const kind = pick(ref.kind, ["link", "note"] as const);
        const v = text(ref.value, 1000).trim();
        return kind && v ? [{ kind, value: v, player: pick(ref.player, players) }] : [];
      })
    : [];
  const sol = (src.solution ?? {}) as Record<string, unknown>;
  c.solution = { approach: text(sol.approach), needs: text(sol.needs, 4000), risks: text(sol.risks, 4000) };
  c.visibility = src.visibility === "committee" ? "committee" : "org";
  c.visibility_reason = text(src.visibility_reason, 1000);
  const dec = (src.declarations ?? {}) as Record<string, unknown>;
  c.declarations = {
    no_personal_data: dec.no_personal_data === true,
    own_work_or_credited: dec.own_work_or_credited === true,
    ip_terms: dec.ip_terms === true,
  };
  return c;
}

function personalDataGuard(c: Canvas) {
  const hits = personalData(c, kfinDomains());
  if (blocks(hits)) {
    throw new SubmissionError(
      422,
      "personal_data",
      hits.map((h) => ({
        field: h.field,
        label: h.match.label,
        action: h.match.action,
        start: h.match.start,
        end: h.match.end,
      })),
    );
  }
  return hits;
}

async function retentionDays() {
  return (await canvasConfig()).canvas.draft_retention_days;
}

export async function createDraft(me: CurrentUser, mode: Mode, input: unknown) {
  const code = owned(me);
  const canvas = sanitiseCanvas(input, mode);
  personalDataGuard(canvas);
  const id = randomUUID();
  const days = await retentionDays();
  await getDb()
    .insertInto("ideas")
    .values({
      id,
      stage: "draft",
      capture_mode: mode,
      contributor_code: code,
      draft_encrypted: encryptJson(canvas, id),
      draft_expires_at: sql<Date>`now() + make_interval(days => ${days})`,
    })
    .execute();
  return { id };
}

async function loadOwned(me: CurrentUser, id: string) {
  if (!/^[0-9a-f-]{36}$/.test(id)) throw new SubmissionError(404, "not_found");
  const row = await getDb()
    .selectFrom("ideas")
    .select(["id", "stage", "capture_mode", "contributor_code", "draft_encrypted", "idea_id", "updated_at"])
    .where("id", "=", id)
    .executeTakeFirst();
  // Someone else's draft looks exactly like a missing one.
  if (!row || row.contributor_code !== owned(me)) throw new SubmissionError(404, "not_found");
  return row;
}

export async function getDraft(me: CurrentUser, id: string) {
  const row = await loadOwned(me, id);
  const { listFor } = await import("./attachments");
  return {
    attachments: await listFor(row.id),
    id: row.id,
    stage: row.stage,
    mode: row.capture_mode as Mode,
    idea_id: row.idea_id,
    canvas: row.draft_encrypted ? decryptJson<Canvas>(row.draft_encrypted, row.id) : null,
    updated_at: row.updated_at,
  };
}

export async function saveDraft(me: CurrentUser, id: string, input: unknown) {
  const row = await loadOwned(me, id);
  if (row.stage !== "draft") throw new SubmissionError(409, "not_a_draft");
  const canvas = sanitiseCanvas(input, row.capture_mode as Mode);
  personalDataGuard(canvas);
  const days = await retentionDays();
  const saved = await getDb()
    .updateTable("ideas")
    .set({
      draft_encrypted: encryptJson(canvas, id),
      draft_expires_at: sql<Date>`now() + make_interval(days => ${days})`,
    })
    .where("id", "=", id)
    .where("stage", "=", "draft")
    .returning("updated_at")
    .executeTakeFirst();
  if (!saved) throw new SubmissionError(409, "not_a_draft");
  return { saved_at: saved.updated_at };
}

export async function submit(me: CurrentUser, id: string, input: unknown) {
  const row = await loadOwned(me, id);
  if (row.stage !== "draft") throw new SubmissionError(409, "already_submitted", { idea_id: row.idea_id });
  const config = await canvasConfig();
  const canvas = finaliseQuick(sanitiseCanvas(input, row.capture_mode as Mode));
  const errors: FieldError[] = validate(canvas, config.canvas);
  if (errors.length) throw new SubmissionError(422, "invalid", errors);
  const warnings = personalDataGuard(canvas);
  const clean = await getDb()
    .selectFrom("attachments")
    .select(sql<number>`count(*)::int`.as("n"))
    .where("idea_uuid", "=", row.id)
    .where("state", "=", "clean")
    .executeTakeFirst();
  const score = strength(canvas, config.canvas_strength, clean?.n ?? 0);

  return getDb()
    .transaction()
    .execute(async (trx) => {
      const year = (
        await sql<{ y: string }>`SELECT to_char(now() AT TIME ZONE ${IST}, 'YYYY') AS y`.execute(trx)
      ).rows[0]!.y;
      // A draft that was submitted before (and sent back to edit) keeps its IDs.
      let ideaId = row.idea_id;
      let submissionId = ideaId ? `SUB-${ideaId.slice(5)}` : null;
      if (!ideaId) {
        const n = (await sql<{ n: number }>`SELECT next_number('IDEA', ${year}) AS n`.execute(trx)).rows[0]!
          .n;
        const number = String(n).padStart(6, "0");
        ideaId = `IDEA-${year}-${number}`;
        submissionId = `SUB-${year}-${number}`;
      }
      const updated = await trx
        .updateTable("ideas")
        .set({
          idea_id: ideaId,
          submission_id: submissionId,
          stage: "scanning",
          kind: canvas.kind,
          category: canvas.value.category,
          play: canvas.value.play,
          basis: canvas.value.basis,
          strength: score.score,
          visibility: canvas.visibility,
          raw_encrypted: encryptJson(canvas, id),
          draft_encrypted: null,
          draft_expires_at: null,
          submitted_at: new Date(),
        })
        .where("id", "=", id)
        .where("stage", "=", "draft")
        .executeTakeFirst();
      if (Number(updated.numUpdatedRows) !== 1) throw new SubmissionError(409, "already_submitted");
      await trx
        .insertInto("jobs")
        .values({
          type: "scan.run",
          payload: JSON.stringify({ idea_uuid: id, idea_id: ideaId }),
          dedupe_key: `scan:${ideaId}`,
        })
        .execute();
      // Voice notes (DEC-096): any recording or text still held for this draft goes now it is shared.
      await trx
        .insertInto("jobs")
        .values({ type: "voice.purge", payload: JSON.stringify({ idea_uuid: id }) })
        .execute();
      return {
        id,
        idea_id: ideaId,
        submission_id: submissionId,
        stage: "scanning" as const,
        strength: score.score,
        next_best: score.nextBest,
        warnings: warnings.map((w) => ({ field: w.field, label: w.match.label })),
      };
    });
}
