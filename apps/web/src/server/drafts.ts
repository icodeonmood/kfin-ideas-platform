/**
 * A-API.drafts, web side (L-DRAFT, BLD-C071). The route handlers check the session and the capability; this file
 * names the owner (user id and contributor code) and the device to the worker, which checks the draft is theirs,
 * masks every message before anything else sees it (DEC-103) and keeps the person's own words sealed. The web app
 * never reads those words from the database: they come back from the worker, to their owner only.
 *
 * Errors follow A-API.conventions/2: `{ error: { code, message, field? } }`, the message ready to show.
 */
import { NextResponse, type NextRequest } from "next/server";

import { BANNERS } from "@/lib/killswitch-routes";

import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";
import { spansToUtf16, type CodePointSpan } from "./hide-offsets";
import { switchStates } from "./killswitch";
import { workerFetch } from "./worker";

export type DeviceKind = "phone" | "laptop";
export type DeviceInfo = { kind: DeviceKind; id: string | null };

const DEVICE_ID = /^[A-Za-z0-9_-]{8,64}$/;
const PHONE_UA = /Mobi|Android|iPhone|iPod|Windows Phone/i;
export const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/** Plain words for each refusal (A-API.conventions/2). The pack's own lines where it has one. */
export const DRAFT_MESSAGES: Record<string, string> = {
  not_found: "We couldn't find that draft.",
  archived: "This draft is archived. Restore it from My ideas to carry on.",
  empty_message: "Type a few words first.",
  too_long: "That's too long. Please make it shorter.",
  too_many_messages: "This draft can't take more messages. Check it and send it, or start a new one.",
  value_required: "Add something here first.",
  value_invalid: "Choose from the list, or type your own.",
  not_editable: "This part can't be changed here.",
  assistant_off: BANNERS["ai.all"],
  save_failed: "Couldn't save. Trying again.",
  /** A voice note sent while voice is off or not in this build: every voice-off line reads the same (BLD-C149). */
  voice_unavailable: BANNERS["capture.voice"],
};
const FALLBACK = "Something went wrong. Please try again.";

/** Capture first (DEC-125, BLD-C212): `ai.all` is off, or `agent.draft-part` alone is off (DEC-143 (g), BLD-B281),
 * the two switches without which the worker runs no draft part (draft/runs.py `ai_on`), so the panel would only
 * fill with parts nobody can work out. Read as the "The assistant is taking a break…" banner reads `ai.all`
 * (components/banners.tsx: the switch table, anything but "on" is off, a missing row too, as the worker's
 * `killswitch.is_on`); a table that cannot be read shows no banner, so Tell it stays in Full mode too. Nothing else
 * turns it on: another switch off keeps Full mode, and so does a run that fails every part. */
export async function captureFirstOn(): Promise<boolean> {
  try {
    const states = await switchStates();
    return states.get("ai.all") !== "on" || states.get("agent.draft-part") !== "on";
  } catch {
    return false;
  }
}

/** "This draft is open on your phone. Carry on here?" (L-DRAFT.autosave/5, NOT DRAWN default). */
export function openElsewhere(device: unknown): string {
  return `This draft is open on your ${device === "phone" ? "phone" : "laptop"}. Carry on here?`;
}

export class DraftApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public extra: Record<string, unknown> = {},
  ) {
    super(code);
  }
}

/** The device asking: the client says which (`X-Device`) and its own opaque id (`X-Device-Id`) for "this device";
 * without the header the user agent decides phone or laptop. */
export function deviceOf(request: NextRequest): DeviceInfo {
  const said = request.headers.get("x-device");
  const kind: DeviceKind =
    said === "phone" || said === "laptop"
      ? said
      : PHONE_UA.test(request.headers.get("user-agent") ?? "")
        ? "phone"
        : "laptop";
  const id = request.headers.get("x-device-id");
  return { kind, id: id && DEVICE_ID.test(id) ? id : null };
}

function owner(me: CurrentUser) {
  if (!me.contributorCode) throw new DraftApiError(403, "forbidden");
  return { user_id: me.id, code: me.contributorCode };
}

function query(me: CurrentUser, device: DeviceInfo, extra: Record<string, string> = {}): string {
  const q = new URLSearchParams({
    user_id: me.id,
    code: me.contributorCode ?? "",
    device_kind: device.kind,
    ...(device.id ? { device_id: device.id } : {}),
    ...extra,
  });
  return q.toString();
}

async function call<T>(path: string, init: RequestInit): Promise<{ status: number; body: T }> {
  let res: Response;
  try {
    // 15 s for a write; a caller's own signal (the stream's 5 s read) wins (BLD-C039).
    res = await workerFetch(path, { ...init, signal: init.signal ?? AbortSignal.timeout(15_000) });
  } catch {
    throw new DraftApiError(503, "save_failed");
  }
  if (res.status === 204) return { status: 204, body: undefined as T };
  const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) {
    const { error, ...extra } = body;
    throw new DraftApiError(
      res.status >= 500 ? 503 : res.status,
      typeof error === "string" ? error : "save_failed",
      extra,
    );
  }
  return { status: res.status, body: body as T };
}

const json = (body: Record<string, unknown>) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const drafts = {
  list: (me: CurrentUser, device: DeviceInfo, archived: boolean) =>
    call(`/internal/drafts?${query(me, device, archived ? { archived: "1" } : {})}`, {}),
  get: (me: CurrentUser, device: DeviceInfo, id: string, open: boolean) =>
    call(`/internal/drafts/${encodeURIComponent(id)}?${query(me, device, open ? { open: "1" } : {})}`, {}),
  live: (me: CurrentUser, device: DeviceInfo, id: string, runId?: string | null) =>
    call<LiveState>(
      `/internal/drafts/${encodeURIComponent(id)}/live?${query(me, device, runId ? { run_id: runId } : {})}`,
      { signal: AbortSignal.timeout(5_000) },
    ),
  create: (me: CurrentUser, device: DeviceInfo, body: Record<string, unknown>) =>
    call("/internal/drafts", json({ ...body, owner: owner(me), device })),
  write: (
    me: CurrentUser,
    device: DeviceInfo,
    method: "POST" | "PATCH",
    path: string,
    body: Record<string, unknown> = {},
  ) =>
    call(`/internal/drafts/${path}`, {
      ...json({ ...body, owner: owner(me), device }),
      method,
    }),
};

/**
 * J-SIMILAR/6a, L-MERGE.request/5 (BLD-C155): whether this is the person's own draft, closed as merged into another
 * idea before it was ever sent (status `merged`, no reference of its own). Such a draft lives on Check it, read-only
 * with "Merged into IDEA-…", so Tell it (`/share/:id`) and Done (`/share/:id/done`) send it there. Someone else's
 * draft, a missing one, a plain draft and a shared idea all answer false, and nothing else changes for them.
 */
export async function isMergedDraft(me: CurrentUser, id: string): Promise<boolean> {
  if (!UUID.test(id) || !me.contributorCode) return false;
  const row = await getDb()
    .selectFrom("ideas")
    .select(["status", "idea_id", "contributor_code"])
    .where("id", "=", id)
    .executeTakeFirst();
  return Boolean(
    row && row.contributor_code === me.contributorCode && row.status === "merged" && row.idea_id === null,
  );
}

/** Known refusals become A-API errors; anything else is rethrown. */
export function draftError(err: unknown): NextResponse {
  if (err instanceof DraftApiError) {
    const { field, device, ...rest } = err.extra;
    const message =
      err.code === "open_elsewhere" ? openElsewhere(device) : (DRAFT_MESSAGES[err.code] ?? FALLBACK);
    return NextResponse.json(
      {
        error: {
          code: err.code,
          message,
          ...(typeof field === "string" ? { field } : {}),
          ...(device ? { device } : {}),
          ...rest,
        },
      },
      { status: err.status, headers: { "Cache-Control": "no-store" } },
    );
  }
  throw err;
}

export const noStore = { "Cache-Control": "no-store" };

const isSpan = (v: unknown): v is CodePointSpan =>
  typeof v === "object" &&
  v !== null &&
  typeof (v as CodePointSpan).start === "number" &&
  typeof (v as CodePointSpan).end === "number";

/**
 * L-HIDE offsets at the web edge (BLD-C121): the worker counts code points, the browser draws the dotted underline in
 * UTF-16 units, and the two part after any emoji. Every `{ text, spans }` in a body leaving for the browser (a draft's
 * messages, the message a write returns, a voice note's words) has its spans converted against its own text with the
 * server's `spansToUtf16` (hide-offsets.ts). The stream's `hidden` event carries no text, so the screen draws only
 * these converted spans. Nothing else in the body changes.
 */
export function spansForBrowser<T>(body: T, depth = 0): T {
  if (depth > 6 || typeof body !== "object" || body === null) return body;
  if (Array.isArray(body)) return body.map((x) => spansForBrowser(x, depth + 1)) as T;
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(body as Record<string, unknown>))
    out[k] = spansForBrowser(v, depth + 1);
  const text = out.text;
  const spans = out.spans;
  if (typeof text === "string" && Array.isArray(spans) && spans.every(isSpan))
    out.spans = spansToUtf16(text, spans);
  return out as T;
}

/** A JSON body, or {} when it is not one. */
export async function bodyOf(request: Request): Promise<Record<string, unknown>> {
  const body: unknown = await request.json().catch(() => ({}));
  return body && typeof body === "object" && !Array.isArray(body) ? (body as Record<string, unknown>) : {};
}

// ---------------------------------------------------------------------------------------------------------------
// The live view the stream reads (`/internal/drafts/:id/live`)
// ---------------------------------------------------------------------------------------------------------------
export interface LivePart {
  state: "waiting" | "updating" | "filled" | "pinned" | "failed";
  value: unknown;
  why: string | null;
  source_quote: string | null;
  took_ms: number | null;
  run_id: string | null;
}
export interface LiveRun {
  id: string;
  state: "running" | "done" | "failed";
  parts: { key: string; mean_ms: number }[];
  part_ms: Record<string, number>;
  receipt: string[];
  suggestions: string[];
  ready: boolean;
  hidden: {
    spans: { start: number; end: number; kind: string }[];
    details: { id: string; kind: string; masked: string; state: string }[];
  };
}
export interface LiveState {
  latest: { id: string; state: string } | null;
  run: LiveRun | null;
  parts?: Record<string, LivePart>;
}
