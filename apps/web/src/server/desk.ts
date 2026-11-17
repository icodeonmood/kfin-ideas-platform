/**
 * The review side's API (A-API.desk, A-API.questions, A-API.committee): each route handler checks the capability,
 * then forwards to the worker's `/internal/*` route with the signed-in person as `user_id`. The worker decides
 * what that person may do to this idea and answers in the pack's error shape,
 * `{ error: { code, message, field? } }`, which is passed through as it is so a message shows under its field.
 */
import { NextResponse, type NextRequest } from "next/server";

import { authorize, signedIn } from "@/server/auth/authorize";
import type { CurrentUser } from "@/server/auth/current";
import { readJson } from "@/server/http";
import { workerFetch } from "@/server/worker";

type Gate = "view_review_queue" | "work_review_queue" | "committee_window" | "signed_in";

async function who(gate: Gate): Promise<CurrentUser | NextResponse> {
  return gate === "signed_in" ? signedIn() : authorize(gate);
}

function path(base: string, me: CurrentUser, query: Record<string, string | null | undefined> = {}): string {
  const qs = new URLSearchParams({ user_id: me.id });
  for (const [k, v] of Object.entries(query)) if (v) qs.set(k, v);
  return `${base}?${qs.toString()}`;
}

/** Field values the worker reads: strings, numbers, booleans, and lists of those or of plain objects. */
function body(raw: Record<string, unknown>, keys: readonly string[]): string {
  const out: Record<string, unknown> = {};
  for (const k of keys) if (raw[k] !== undefined) out[k] = raw[k];
  return JSON.stringify(out);
}

/** What the browser gets when the worker cannot be reached or answers with something that is not JSON: the pack's
 * error shape (A-API.conventions/2) and F-COPY's failure line, never the worker's own text. */
export const WORKER_FAILED = {
  error: { code: "desk_unavailable", message: "That didn’t go through. Try again in a moment." },
} as const;

function failed(): NextResponse {
  return NextResponse.json(WORKER_FAILED, { status: 502, headers: { "Cache-Control": "no-store" } });
}

export async function forward(workerPath: string, init: RequestInit = {}): Promise<NextResponse> {
  let res: Response;
  let text: string;
  try {
    res = await workerFetch(workerPath, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    });
    text = await res.text();
  } catch {
    return failed();
  }
  let json: unknown = null;
  if (text) {
    try {
      json = JSON.parse(text) as unknown;
    } catch {
      return failed();
    }
  }
  return NextResponse.json(json, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

/** GET handler: the gate, the worker path built from the route's params and the request's query. */
export function getRoute(gate: Gate, workerPath: (id: string) => string, queryKeys: readonly string[] = []) {
  return async (request: NextRequest, ctx: { params: Promise<{ id?: string }> }) => {
    const me = await who(gate);
    if (me instanceof NextResponse) return me;
    const id = (await ctx.params).id ?? "";
    const q = Object.fromEntries(queryKeys.map((k) => [k, request.nextUrl.searchParams.get(k)]));
    return forward(path(workerPath(encodeURIComponent(id)), me, q));
  };
}

/** POST or PUT handler: the gate, the worker path and the body fields passed on. */
export function writeRoute(
  gate: Gate,
  method: "POST" | "PUT",
  workerPath: (id: string) => string,
  bodyKeys: readonly string[] = [],
) {
  return async (request: NextRequest, ctx: { params: Promise<{ id?: string }> }) => {
    const me = await who(gate);
    if (me instanceof NextResponse) return me;
    const id = (await ctx.params).id ?? "";
    const raw = bodyKeys.length ? await readJson(request) : {};
    return forward(path(workerPath(encodeURIComponent(id)), me), {
      method,
      body: body(raw, bodyKeys),
    });
  };
}
