/**
 * Sorting and sending, web side (L-SORT, L-SUBMIT; lane C). The worker owns the rules (`services/worker/submit`):
 * these handlers check the session, the capability and the kill switches (in the proxy, and again in each route),
 * then pass the signed-in person's id and the body through. Answers keep the A-API error shape
 * (`{ error: { code, message, field? } }`); no text is logged here (non-negotiable 3).
 */
import { NextResponse } from "next/server";

import { IDEMPOTENCY_HEADER, type ConfigResponse } from "@/lib/contracts/api";

import type { CurrentUser } from "./auth/current";
import { promises } from "./promises";
import { workerFetch } from "./worker";

/** A draft's row id, or a shared idea's reference. */
const KEY = /^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|IDEA-[0-9]{4}-[0-9]{6})$/;
/** A-API.conventions/3: the key a client sends with a write that creates something. */
const IDEMPOTENCY = /^[A-Za-z0-9_.:-]{8,200}$/;
const NOT_FOUND = { error: { code: "not_found", message: "We can’t find that idea." } };
/** V-FIELDS.checkit/13: Submit's own failure line; every other call here says the general one. */
export const SEND_FAILED = {
  error: {
    code: "send_failed",
    message: "Couldn’t send. Your draft is safe. Check your connection, then try again.",
  },
};
const FAILED = { error: { code: "unavailable", message: "Something went wrong. Try again." } };

export const MAX_BODY_BYTES = 64 * 1024;

type Method = "GET" | "PATCH" | "POST" | "PUT" | "DELETE";

async function relay(
  path: string,
  method: Method,
  body?: unknown,
  failed: typeof FAILED = FAILED,
): Promise<NextResponse> {
  let res: Response;
  try {
    res = await workerFetch(path, {
      method,
      ...(body === undefined
        ? {}
        : { body: JSON.stringify(body), headers: { "Content-Type": "application/json" } }),
    });
  } catch {
    return NextResponse.json(failed, { status: 502 });
  }
  const data = (await res.json().catch(() => null)) as unknown;
  if (data === null || typeof data !== "object") return NextResponse.json(failed, { status: 502 });
  if (res.status === 401 || res.status >= 500) return NextResponse.json(failed, { status: 502 });
  return NextResponse.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

function withUser(path: string, me: CurrentUser, extra: Record<string, string> = {}): string {
  const q = new URLSearchParams({ user_id: me.id, ...extra });
  return `${path}?${q.toString()}`;
}

/** A JSON body of at most `MAX_BODY_BYTES`, or null when it is missing, too big or not JSON. */
export async function jsonBody(request: Request): Promise<unknown> {
  const text = await request.text().catch(() => "");
  if (!text || text.length > MAX_BODY_BYTES) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

export function badKey(): NextResponse {
  return NextResponse.json(NOT_FOUND, { status: 404 });
}

export const isKey = (key: string): boolean => KEY.test(key);

/** `GET /drafts/:id/sorting`: the suggested sorting, or what the person confirmed or changed (L-SORT). */
export function readSorting(me: CurrentUser, draftId: string) {
  if (!isKey(draftId)) return Promise.resolve(badKey());
  return relay(withUser(`/internal/drafts/${encodeURIComponent(draftId)}/sorting`, me), "GET");
}

/** `PATCH /drafts/:id/sorting` with `{affects?, kind?, area?, brings?}` or `{confirm: true}` (L-SORT.rules/2–3). */
export function patchSorting(me: CurrentUser, draftId: string, body: unknown) {
  if (!isKey(draftId)) return Promise.resolve(badKey());
  return relay(withUser(`/internal/drafts/${encodeURIComponent(draftId)}/sorting`, me), "PATCH", body);
}

/**
 * `PUT /drafts/:id/fix` with the `Fix` fields (S-05.fix): "Add my fix", or `included: false` for "Close, and keep
 * what you wrote". Returns `Fix` with `ready_count`; amounts come back normalised in `Range.text` (L-WORTH/1).
 */
export function putFix(me: CurrentUser, draftId: string, body: unknown) {
  if (!isKey(draftId)) return Promise.resolve(badKey());
  return relay(withUser(`/internal/drafts/${encodeURIComponent(draftId)}/fix`, me), "PUT", body);
}

/** `DELETE /drafts/:id/fix`: "Remove" (S-05 part 5). */
export function removeFix(me: CurrentUser, draftId: string) {
  if (!isKey(draftId)) return Promise.resolve(badKey());
  return relay(withUser(`/internal/drafts/${encodeURIComponent(draftId)}/fix`, me), "DELETE");
}

/** `PUT /drafts/:id/helpers` `{ picks, text? }`: "Who would help" (S-05 part 6). */
export function putHelpers(me: CurrentUser, draftId: string, body: unknown) {
  if (!isKey(draftId)) return Promise.resolve(badKey());
  return relay(withUser(`/internal/drafts/${encodeURIComponent(draftId)}/helpers`, me), "PUT", body);
}

/** `GET /drafts/:id/send`: the Send part's last look, the declaration and what would stop Submit (L-SUBMIT.pre). */
export function sendView(me: CurrentUser, draftId: string) {
  if (!isKey(draftId)) return Promise.resolve(badKey());
  return relay(withUser(`/internal/drafts/${encodeURIComponent(draftId)}/send`, me), "GET");
}

/** `POST /drafts/:id/submit` `{declaration_version}` with an `Idempotency-Key` (L-SUBMIT.send). */
export function submitDraft(me: CurrentUser, draftId: string, body: unknown, headers: Headers) {
  if (!isKey(draftId)) return Promise.resolve(badKey());
  const key = headers.get(IDEMPOTENCY_HEADER);
  if (key !== null && !IDEMPOTENCY.test(key)) {
    return Promise.resolve(
      NextResponse.json(
        { error: { code: "idempotency_key_bad", message: "Something went wrong. Try again." } },
        { status: 400 },
      ),
    );
  }
  const extra: Record<string, string> = key ? { idempotency_key: key } : {};
  return relay(
    withUser(`/internal/drafts/${encodeURIComponent(draftId)}/submit`, me, extra),
    "POST",
    body,
    SEND_FAILED,
  );
}

/** `GET /ideas/:id/edit`: everything the edit page shows (S-06B, L-SUBMIT.edit). */
export function editPage(me: CurrentUser, ideaId: string) {
  if (!isKey(ideaId)) return Promise.resolve(badKey());
  return relay(withUser(`/internal/ideas/${encodeURIComponent(ideaId)}/edit`, me), "GET");
}

/** The edit page's Save: any of title, summary, often, sorting, fix, helpers (A-API `PATCH /ideas/:id`). */
export function saveEdit(me: CurrentUser, ideaId: string, body: unknown) {
  if (!isKey(ideaId)) return Promise.resolve(badKey());
  return relay(withUser(`/internal/ideas/${encodeURIComponent(ideaId)}/edit`, me), "PATCH", body);
}

/** `GET /ideas/:id/versions` for "Draft history": the sharer, the review desk and the Ones Committee. */
export function versions(me: CurrentUser, ideaId: string) {
  if (!isKey(ideaId)) return Promise.resolve(badKey());
  return relay(withUser(`/internal/ideas/${encodeURIComponent(ideaId)}/versions`, me), "GET");
}

type SortingConfig = {
  sorting: NonNullable<ConfigResponse["sorting"]["controls"]>;
  declaration: NonNullable<ConfigResponse["declaration"]>;
  windows: { review_working_days: number; edit_window_days: number };
};

/**
 * `GET /config` (A-API.config): the numbers the copy shows (P-PRODUCT.promises) and the sorting lists. Lane C's
 * part; uploads, placeholders and flags join it from their lanes.
 */
export async function publicConfig(): Promise<ConfigResponse> {
  const [p, res] = await Promise.all([promises(), workerFetch("/internal/config/sorting")]);
  if (!res.ok) throw new Error("config_unavailable");
  const c = (await res.json()) as SortingConfig;
  return {
    promises: {
      min_chars: p.draft.min_chars_to_check,
      voice_max_seconds: p.voice.max_seconds,
      review_working_days: p.review.decide_by_working_days,
      edit_window_days: p.edit_window.max_days,
      answer_options_days: p.questions.answer_options_days,
      answer_default_days: p.questions.answer_default_days,
      decision_reason_min_chars: p.notes.decision_reason_min_chars,
      reversal_note_min_chars: p.notes.reversal_note_min_chars,
      teamup_note_min_chars: p.notes.teamup_note_min_chars,
      merge_note_min_chars: p.notes.merge_note_min_chars,
      committee_window_days: p.committee_window.days,
      not_now_return_options_months: p.not_now.return_options_months,
      not_now_return_default_months: p.not_now.return_default_months,
    },
    sorting: {
      affects: c.sorting.affects.all,
      areas: c.sorting.area.all,
      brings: c.sorting.brings.options.map((o) => o.value),
      helpers: c.sorting.helpers,
      controls: c.sorting,
    },
    declaration: c.declaration,
  };
}
