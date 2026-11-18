/**
 * The review side's API (A-API.desk, A-API.questions, A-API.committee): each route handler checks the capability,
 * then forwards to the worker's `/internal/*` route with the signed-in person as `user_id`. The worker decides
 * what that person may do to this idea and answers in the pack's error shape,
 * `{ error: { code, message, field? } }`, which is passed through as it is so a message shows under its field.
 */
import { NextResponse, type NextRequest } from "next/server";

import { SEARCH_MAX } from "@/lib/search-memory";
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

/** The route's `[id]`, or "" for a route without one: Next passes no `params` there (GET /api/desk, /api/committee). */
export async function paramId(ctx?: { params?: Promise<{ id?: string }> }): Promise<string> {
  return (await ctx?.params)?.id ?? "";
}

/** GET handler: the gate, the worker path built from the route's params and the request's query. */
export function getRoute(gate: Gate, workerPath: (id: string) => string, queryKeys: readonly string[] = []) {
  return async (request: NextRequest, ctx?: { params?: Promise<{ id?: string }> }) => {
    const me = await who(gate);
    if (me instanceof NextResponse) return me;
    const id = await paramId(ctx);
    const q = Object.fromEntries(queryKeys.map((k) => [k, request.nextUrl.searchParams.get(k)]));
    return forward(path(workerPath(encodeURIComponent(id)), me, q));
  };
}

/** POST handler for a read whose words must stay out of every URL, a search (DEC-110): the gate, then the body's
 * string fields passed on in the worker's POST body, each cut at 200 characters (the search box's limit, kept on the
 * server too). Anything that is not a string is left out. */
export function searchRoute(gate: Gate, workerPath: (id: string) => string, bodyKeys: readonly string[]) {
  return async (request: NextRequest, ctx?: { params?: Promise<{ id?: string }> }) => {
    const me = await who(gate);
    if (me instanceof NextResponse) return me;
    const id = await paramId(ctx);
    const raw = await readJson(request);
    const out: Record<string, string> = {};
    for (const k of bodyKeys) {
      const v = raw[k];
      if (typeof v === "string") out[k] = v.slice(0, SEARCH_MAX);
    }
    return forward(path(workerPath(encodeURIComponent(id)), me), {
      method: "POST",
      body: JSON.stringify(out),
    });
  };
}

/** POST or PUT handler: the gate, the worker path and the body fields passed on. */
export function writeRoute(
  gate: Gate,
  method: "POST" | "PUT",
  workerPath: (id: string) => string,
  bodyKeys: readonly string[] = [],
) {
  return async (request: NextRequest, ctx?: { params?: Promise<{ id?: string }> }) => {
    const me = await who(gate);
    if (me instanceof NextResponse) return me;
    const id = await paramId(ctx);
    const raw = bodyKeys.length ? await readJson(request) : {};
    return forward(path(workerPath(encodeURIComponent(id)), me), {
      method,
      body: body(raw, bodyKeys),
    });
  };
}

// ---------------------------------------------------------------------------------------------------------------
// Server-side reads for the review side's pages (the page renders with data; the client then talks to /api).
// ---------------------------------------------------------------------------------------------------------------

/** One read from the worker for a server component; null when the worker says it does not exist, or that this
 * person may not read it (403: an admin holds the web's desk capabilities, and the worker refuses them, BLD-B232),
 * so the page sends them home or shows not found rather than failing. */
export async function deskRead<T>(
  me: CurrentUser,
  workerPath: string,
  query: Record<string, string | null | undefined> = {},
): Promise<T | null> {
  const res = await workerFetch(path(workerPath, me, query));
  if (res.status === 404 || res.status === 403) return null;
  if (!res.ok) throw new Error(`worker answered ${res.status}`);
  return (await res.json()) as T;
}

/** L-REVIEW.open/1, from the reviewer's page before its read: the first open by a reviewer closes the sharer's edit
 * window. The worker refuses anyone who is not on the desk; a failure here never stops the page from rendering. */
export async function deskOpen(me: CurrentUser, ideaId: string): Promise<void> {
  try {
    await workerFetch(path(`/internal/desk/ideas/${encodeURIComponent(ideaId)}/open`, me), {
      method: "POST",
    });
  } catch {
    // the read that follows shows the idea as it is
  }
}
