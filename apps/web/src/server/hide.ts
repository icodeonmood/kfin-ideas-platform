/**
 * L-HIDE, web side (lane C, BLD-C060). The worker does all the hiding: it alone can read the vault and the person's
 * own words (non-negotiable 6). This module checks who is asking, finds the idea, and passes IDs and offsets on.
 *
 * - `POST /api/desk/ideas/:id/hide` (S-R2 "Hide this", L-HIDE.rules/7): the review desk and the Ones Committee.
 * - `POST /api/drafts/:id/hidden/:hid/show` and `/hide` (C-HIDDEN "Show it", "Hide it", L-HIDE.rules/6): the person
 *   whose words they are, only.
 * Errors follow A-API.conventions/2: `{ error: { code, message } }`. Messages never echo the person's text.
 */
import { NextResponse } from "next/server";

import type { ApiError } from "@/lib/contracts/api";
import type { HiddenDetail, ShowReason } from "@/lib/contracts";

import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";
import { workerFetch } from "./worker";

export type HideErrorCode =
  | "forbidden"
  | "not_found"
  | "range_invalid"
  | "already_hidden"
  | "reason_required"
  | "hide_failed";

export const HIDE_MESSAGES: Record<HideErrorCode, string> = {
  forbidden: "Only the review desk and the Ones Committee can hide text.",
  not_found: "We couldn't find that. It may have changed. Refresh and try again.",
  range_invalid: "Select only the words to hide, then try again.",
  already_hidden: "That is already hidden from everyone.",
  reason_required: "Choose what it is first.",
  hide_failed: "We couldn't do that just now. Please try again.",
};

const STATUS: Record<HideErrorCode, number> = {
  forbidden: 403,
  not_found: 404,
  range_invalid: 400,
  already_hidden: 409,
  reason_required: 400,
  hide_failed: 502,
};

export const SHOW_REASONS: readonly ShowReason[] = [
  "scheme_or_product_code",
  "internal_reference",
  "made_up_example",
] as const;

export const DESK_SOURCE_KINDS = ["part", "message", "answer", "title"] as const;
export type DeskSourceKind = (typeof DESK_SOURCE_KINDS)[number];

export class HideError extends Error {
  constructor(public code: HideErrorCode) {
    super(code);
  }
}

export function hideErrorResponse(err: unknown): NextResponse<ApiError<HideErrorCode>> {
  if (!(err instanceof HideError)) throw err;
  return NextResponse.json(
    { error: { code: err.code, message: HIDE_MESSAGES[err.code] } },
    { status: STATUS[err.code], headers: { "Cache-Control": "no-store" } },
  );
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const IDEA_REF = /^IDEA-[0-9]{4}-[0-9]{6}$/;

/** An idea by its row id (UUID) or its reference ("IDEA-2026-001481"). */
async function findIdea(id: string) {
  const query = getDb().selectFrom("ideas").select(["id", "idea_id", "status", "contributor_code"]);
  if (UUID.test(id)) return query.where("id", "=", id).executeTakeFirst();
  if (IDEA_REF.test(id)) return query.where("idea_id", "=", id).executeTakeFirst();
  return undefined;
}

async function callWorker(path: string, body: Record<string, unknown>): Promise<HiddenDetail> {
  const res = await workerFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const out = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) {
    const code = String(out.error ?? "");
    throw new HideError(code in STATUS ? (code as HideErrorCode) : "hide_failed");
  }
  return out as unknown as HiddenDetail;
}

/** The desk's and committee's "Hide this" on any text they read on a shared idea. */
export async function deskHide(me: CurrentUser, ideaId: string, body: Record<string, unknown>) {
  const idea = await findIdea(ideaId);
  if (!idea || idea.status === "draft") throw new HideError("not_found");
  const source = (body.source ?? {}) as Record<string, unknown>;
  const kind = source.kind;
  const sourceId = source.id;
  const { start, end } = body;
  if (
    typeof kind !== "string" ||
    !(DESK_SOURCE_KINDS as readonly string[]).includes(kind) ||
    typeof sourceId !== "string" ||
    sourceId.length === 0 ||
    sourceId.length > 100 ||
    !Number.isInteger(start) ||
    !Number.isInteger(end)
  )
    throw new HideError("range_invalid");
  return callWorker(`/internal/hide/desk/${encodeURIComponent(idea.id)}`, {
    source: { kind, id: sourceId },
    start,
    end,
    by: me.id,
  });
}

/** The person's own idea or draft; anyone else's looks exactly like a missing one. */
async function ownIdea(me: CurrentUser, draftId: string) {
  const idea = await findIdea(draftId);
  if (!idea || !me.contributorCode || idea.contributor_code !== me.contributorCode)
    throw new HideError("not_found");
  return idea;
}

export async function showHidden(me: CurrentUser, draftId: string, hid: string, reason: unknown) {
  if (typeof reason !== "string" || !(SHOW_REASONS as readonly string[]).includes(reason))
    throw new HideError("reason_required");
  const idea = await ownIdea(me, draftId);
  if (!UUID.test(hid)) throw new HideError("not_found");
  return callWorker(`/internal/hide/${encodeURIComponent(idea.id)}/details/${hid}/show`, { reason, by: me.id });
}

export async function hideAgain(me: CurrentUser, draftId: string, hid: string) {
  const idea = await ownIdea(me, draftId);
  if (!UUID.test(hid)) throw new HideError("not_found");
  return callWorker(`/internal/hide/${encodeURIComponent(idea.id)}/details/${hid}/hide`, { by: me.id });
}
