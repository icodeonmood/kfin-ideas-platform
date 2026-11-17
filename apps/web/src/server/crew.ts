/**
 * Find your crew (A-API.team-up `GET /crew` and the passes, L-CREW) and lane F's other reads: each route handler
 * checks the session, then forwards to the worker's `/internal/*` route with the signed-in person as `user_id`.
 * The worker decides what that person may see and answers in the pack's error shape,
 * `{ error: { code, message, field? } }`, which is passed through as it is.
 */
import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { readJson } from "@/server/http";
import { workerFetch } from "@/server/worker";

/** The deck's filters (L-CREW/5); each may repeat ("location=Hyderabad&location=Pune"). */
export const CREW_FILTERS = ["location", "category", "status", "team_size", "looking_for"] as const;

/**
 * The worker path for a read: `user_id` first, then only the named query keys, repeated keys kept in order,
 * empty values and anything else dropped (a caller cannot pass someone else's `user_id`).
 */
export function workerPath(
  base: string,
  userId: string,
  params: URLSearchParams,
  repeated: readonly string[] = [],
  single: readonly string[] = [],
): string {
  const qs = new URLSearchParams({ user_id: userId });
  for (const key of repeated) {
    for (const value of params.getAll(key)) {
      const v = value.trim();
      if (v) qs.append(key, v.slice(0, 120));
    }
  }
  for (const key of single) {
    const v = params.get(key)?.trim();
    if (v) qs.set(key, v.slice(0, 120));
  }
  return `${base}?${qs.toString()}`;
}

/** The pass body: the idea's reference only. */
export function passBody(raw: Record<string, unknown>): string {
  return JSON.stringify(typeof raw.idea_id === "string" ? { idea_id: raw.idea_id } : {});
}

/** The answer when the worker cannot be reached or does not answer in JSON (a plain-text 500, a proxy page). */
export const UNAVAILABLE = { error: { code: "unavailable", message: "" } } as const;

export async function forward(path: string, init: RequestInit = {}): Promise<NextResponse> {
  const headers = { "Cache-Control": "no-store" };
  let res: Response;
  try {
    res = await workerFetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    });
  } catch {
    return NextResponse.json(UNAVAILABLE, { status: 502, headers });
  }
  let json: unknown = null;
  try {
    const text = await res.text();
    json = text ? (JSON.parse(text) as unknown) : null;
  } catch {
    return NextResponse.json(UNAVAILABLE, { status: 502, headers });
  }
  return NextResponse.json(json, { status: res.status, headers });
}

/** GET handler for a signed-in read: the worker path and the query keys it takes. */
export function signedInRead(base: string, repeated: readonly string[] = [], single: readonly string[] = []) {
  return async (request: NextRequest) => {
    const me = await signedIn();
    if (me instanceof NextResponse) return me;
    return forward(workerPath(base, me.id, request.nextUrl.searchParams, repeated, single));
  };
}

/** POST handler for the passes: `/internal/crew/pass`, `/undo`, `/reset`. Only "pass" reads a body. */
export function passRoute(base: string, withBody = false) {
  return async (request: NextRequest) => {
    const me = await signedIn();
    if (me instanceof NextResponse) return me;
    const body = withBody ? passBody(await readJson(request)) : "{}";
    return forward(`${base}?${new URLSearchParams({ user_id: me.id }).toString()}`, {
      method: "POST",
      body,
    });
  };
}
