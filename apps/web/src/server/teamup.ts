/**
 * Team-up, draft merge requests and crews (A-API.team-up, A-API.drafts merge-request; L-TEAMUP, L-MERGE.request).
 * Each route handler checks the session, then forwards to the worker's `/internal/*` route with the signed-in
 * person as `user_id`. The worker decides what that person may do (only the requester withdraws, only the idea's
 * lead answers or removes) and answers in the pack's error shape, `{ error: { code, message, field? } }`, passed
 * through as it is so a message shows under its field. Creates pass `Idempotency-Key` on (A-API.conventions/3).
 */
import { NextResponse, type NextRequest } from "next/server";

import { IDEMPOTENCY_HEADER } from "@/lib/contracts/api";
import { signedIn } from "@/server/auth/authorize";
import type { CurrentUser } from "@/server/auth/current";
import { readJson } from "@/server/http";
import { workerFetch } from "@/server/worker";

type Params = { params: Promise<Record<string, string | undefined>> };

function path(base: string, me: CurrentUser): string {
  return `${base}?${new URLSearchParams({ user_id: me.id }).toString()}`;
}

/** Only the named fields go on to the worker. */
export function pick(raw: Record<string, unknown>, keys: readonly string[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const k of keys) if (raw[k] !== undefined) out[k] = raw[k];
  return out;
}

async function forward(workerPath: string, init: RequestInit = {}): Promise<NextResponse> {
  const res = await workerFetch(workerPath, init);
  const text = await res.text();
  let json: unknown = null;
  try {
    json = text ? (JSON.parse(text) as unknown) : null;
  } catch {
    json = { error: { code: "worker_error", message: "Something went wrong. Please try again." } };
  }
  return NextResponse.json(json, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

/** The route's `[id]` and `[member]` segments, escaped for the worker's path. */
async function segments(ctx: Params): Promise<[string, string]> {
  const p = await ctx.params;
  return [encodeURIComponent(p.id ?? ""), encodeURIComponent(p.member ?? "")];
}

/** A read: the session, then the worker path built from the route's segments. */
export function teamupGet(workerPath: (id: string, member: string) => string) {
  return async (_request: NextRequest, ctx: Params): Promise<NextResponse> => {
    const me = await signedIn();
    if (me instanceof NextResponse) return me;
    const [id, member] = await segments(ctx);
    return forward(path(workerPath(id, member), me));
  };
}

/** A write: the session, the worker path, the body fields passed on, and the Idempotency-Key if sent. */
export function teamupWrite(
  method: "POST" | "DELETE",
  workerPath: (id: string, member: string) => string,
  bodyKeys: readonly string[] = [],
) {
  return async (request: NextRequest, ctx: Params): Promise<NextResponse> => {
    const me = await signedIn();
    if (me instanceof NextResponse) return me;
    const [id, member] = await segments(ctx);
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const key = request.headers.get(IDEMPOTENCY_HEADER);
    if (key) headers[IDEMPOTENCY_HEADER] = key;
    const init: RequestInit = { method, headers };
    if (method === "POST")
      init.body = JSON.stringify(pick(bodyKeys.length ? await readJson(request) : {}, bodyKeys));
    return forward(path(workerPath(id, member), me), init);
  };
}
