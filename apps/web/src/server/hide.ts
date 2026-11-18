/**
 * L-HIDE, web side (lane C, BLD-C060). The worker does all the hiding: it alone can read the vault and the person's
 * own words (non-negotiable 6). This module checks who is asking, finds the idea, and passes IDs and offsets on.
 *
 * - `POST /api/desk/ideas/:id/hide` (S-R2 "Hide this", L-HIDE.rules/7): the review desk and the Ones Committee.
 * - `POST /api/drafts/:id/hidden/:hid/show` and `/hide` (C-HIDDEN "Show it", "Hide it", L-HIDE.rules/6): the person
 *   whose words they are, only.
 * Errors follow A-API.conventions/2: `{ error: { code, message } }`. Messages never echo the person's text.
 * Offsets: the browser's "Hide this" range is in UTF-16 units and goes on as `units: "utf16"`; spans going out are
 * converted with `spansToUtf16` (`hide-offsets.ts`, BLD-C068). The page also sends `selected`, the masked words it
 * selected (at most `SELECTED_MAX` UTF-16 units); the worker, which alone holds the text, compares them with the
 * text at that range after converting the offsets, and refuses with `stale` (409) when the text changed under the
 * selection. A reviewer never hides on their own idea or one their contribution was merged into (`forbidden`).
 */
import { NextResponse } from "next/server";

import type { ApiError } from "@/lib/contracts/api";
import type { HiddenDetail, ShowReason } from "@/lib/contracts";

import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";
import { workerFetch } from "./worker";

export { codePointsToUtf16, spansToUtf16, utf16ToCodePoints } from "./hide-offsets";

export type HideErrorCode =
  | "forbidden"
  | "not_found"
  | "range_invalid"
  | "already_hidden"
  | "stale"
  | "selection_too_long"
  | "reason_required"
  | "hide_failed";

export const HIDE_MESSAGES: Record<HideErrorCode, string> = {
  forbidden: "The review desk hid this, so it stays hidden.",
  not_found: "We couldn't find that. It may have changed. Refresh and try again.",
  range_invalid: "Select only the words to hide, then try again.",
  already_hidden: "That is already hidden from everyone.",
  stale: "The page changed. Select again.",
  selection_too_long: "That’s too much to hide at once. Select only the words to hide.",
  reason_required: "Choose what it is first.",
  hide_failed: "We couldn't do that just now. Please try again.",
};

/** The desk's `forbidden`: the reviewer's own idea, or one their contribution was merged into (lane B's words). */
export const OWN_IDEA = "This is your own idea. Another reviewer takes it.";

const STATUS: Record<HideErrorCode, number> = {
  forbidden: 403,
  not_found: 404,
  range_invalid: 400,
  already_hidden: 409,
  stale: 409,
  selection_too_long: 422,
  reason_required: 400,
  hide_failed: 502,
};

/** The longest `selected` the desk may send, in UTF-16 units: twice the longest text one part holds (a message of
 * 5,000 characters, V-FIELDS.submit/2), so a whole long text always reaches the worker's own checks. */
export const SELECTED_MAX = 10_000;

export const SHOW_REASONS: readonly ShowReason[] = [
  "scheme_or_product_code",
  "internal_reference",
  "made_up_example",
] as const;

export const DESK_SOURCE_KINDS = ["part", "message", "answer", "title", "conversation", "fix"] as const;
export type DeskSourceKind = (typeof DESK_SOURCE_KINDS)[number];

export class HideError extends Error {
  constructor(
    public code: HideErrorCode,
    public words?: string,
  ) {
    super(code);
  }
}

export function hideErrorResponse(err: unknown): NextResponse<ApiError<HideErrorCode>> {
  if (!(err instanceof HideError)) throw err;
  return NextResponse.json(
    { error: { code: err.code, message: err.words ?? HIDE_MESSAGES[err.code] } },
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
    const err = out.error;
    const code =
      typeof err === "string"
        ? err
        : err && typeof err === "object"
          ? String((err as { code?: unknown }).code ?? "")
          : "";
    throw new HideError(code in STATUS ? (code as HideErrorCode) : "hide_failed");
  }
  return out as unknown as HiddenDetail;
}

/**
 * The desk's and committee's "Hide this" on any text they read on a shared idea. Body `{ source: { kind, id }, start,
 * end, selected? }`: `selected` is the masked words the page selected, compared by the worker (`stale` when the text
 * changed). Never on the reviewer's own idea or one their contribution was merged into: the worker refuses both
 * (`forbidden`, audited), and the answer carries lane B's words for it (`OWN_IDEA`).
 */
export async function deskHide(me: CurrentUser, ideaId: string, body: Record<string, unknown>) {
  const idea = await findIdea(ideaId);
  if (!idea || idea.status === "draft") throw new HideError("not_found");
  const source = (body.source ?? {}) as Record<string, unknown>;
  const kind = source.kind;
  const sourceId = source.id;
  const { start, end, selected } = body;
  if (
    typeof kind !== "string" ||
    !(DESK_SOURCE_KINDS as readonly string[]).includes(kind) ||
    typeof sourceId !== "string" ||
    sourceId.length === 0 ||
    sourceId.length > 100 ||
    !Number.isInteger(start) ||
    !Number.isInteger(end) ||
    (selected !== undefined && selected !== null && typeof selected !== "string")
  )
    throw new HideError("range_invalid");
  if (typeof selected === "string" && selected.length > SELECTED_MAX)
    throw new HideError("selection_too_long");
  try {
    return await callWorker(`/internal/hide/desk/${encodeURIComponent(idea.id)}`, {
      source: { kind, id: sourceId },
      start,
      end,
      units: "utf16", // the browser's offsets; the worker converts them against the text the reviewer read
      ...(typeof selected === "string" ? { selected } : {}),
      by: me.id,
    });
  } catch (err) {
    // The worker's only `forbidden` here: the reviewer's own idea or one their contribution was merged into, the rule
    // of lane B's `refuse_own`. It decides (and audits) both, so every refusal leaves one trace.
    if (err instanceof HideError && err.code === "forbidden") throw new HideError("forbidden", OWN_IDEA);
    throw err;
  }
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
  return callWorker(`/internal/hide/${encodeURIComponent(idea.id)}/details/${hid}/show`, {
    reason,
    by: me.id,
  });
}

export async function hideAgain(me: CurrentUser, draftId: string, hid: string) {
  const idea = await ownIdea(me, draftId);
  if (!UUID.test(hid)) throw new HideError("not_found");
  return callWorker(`/internal/hide/${encodeURIComponent(idea.id)}/details/${hid}/hide`, { by: me.id });
}
