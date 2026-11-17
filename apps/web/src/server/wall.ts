/**
 * The Wall, the Ones and Profile, web side (lane E; A-API.wall, A-API.ones, A-API.ones-posts, A-API.me).
 *
 * Each route handler has already checked who is asking. This module forwards to the worker's `/internal` routes
 * (services/worker/wall/routes.py) with the signed-in person's own id, never an id from the request, and hands back
 * the worker's answer as it is: the body is screen-ready, and a refusal is already in the pack's shape
 * `{ error: { code, message, field? } }` (A-API.conventions/2) with V-FIELDS copy, never a person's own words.
 * Anything else (a worker that cannot be reached, a body in another shape) becomes a clean pack-shaped error the
 * screen can show. Logs carry the event and the status only (non-negotiable 3).
 */
import { NextResponse } from "next/server";

import { isEnumValue } from "@/lib/contracts/enums";
import { BANNERS, type SwitchName } from "@/lib/killswitch-routes";

import type { CurrentUser } from "./auth/current";
import { log } from "./log";
import { workerFetch } from "./worker";

/** V-FIELDS.one/5: a switch that did not save flips back with this under it (S-H6.rules/1, NOT DRAWN default). */
export const SAVE_FAILED = "Couldn't save that. Try again.";

type Method = "GET" | "PUT" | "POST" | "PATCH";
type PackError = { error: { code: string; message: string; field?: string } & Record<string, unknown> };

const NO_STORE = { "Cache-Control": "no-store" };

export function packError(status: number, code: string, message = "", field?: string): NextResponse {
  const error: PackError["error"] = { code, message, ...(field ? { field } : {}) };
  return NextResponse.json({ error }, { status, headers: NO_STORE });
}

function isPackError(body: unknown): body is PackError {
  if (!body || typeof body !== "object") return false;
  const error = (body as { error?: unknown }).error;
  return !!error && typeof error === "object" && typeof (error as { code?: unknown }).code === "string";
}

const FALLBACK_CODE: Record<number, string> = { 400: "bad_request", 404: "not_found", 422: "bad_request" };

/**
 * Calls the worker and answers with its status and body. `failMessage` and `field` shape the error when the
 * worker cannot answer (a settings switch names itself, so the screen flips that switch back).
 */
async function relay(
  path: string,
  { method = "GET", body, failMessage = "", field }: { method?: Method; body?: unknown; failMessage?: string; field?: string } = {},
): Promise<NextResponse> {
  let res: Response;
  try {
    res = await workerFetch(
      path,
      method === "GET"
        ? {}
        : { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) },
    );
  } catch {
    log.error("wall.worker_unreachable", { method });
    return packError(503, "try_again", failMessage, field);
  }
  const out: unknown = await res.json().catch(() => null);
  if (res.ok && out !== null) return NextResponse.json(out, { status: res.status, headers: NO_STORE });
  if (isPackError(out)) {
    if (out.error.code === "paused") {
      // A kill switch the worker checked (§7.6): its plain-words notice, as the proxy gives for its own checks.
      const banner = BANNERS[String(out.error.switch) as SwitchName];
      out.error.message = out.error.message || banner || "";
    }
    return NextResponse.json(out, { status: res.status, headers: NO_STORE });
  }
  log.error("wall.worker_failed", { method, status: res.status });
  return res.status >= 500 || res.ok
    ? packError(503, "try_again", failMessage, field)
    : packError(res.status, FALLBACK_CODE[res.status] ?? "refused", failMessage, field);
}

const as = (me: CurrentUser) => `user_id=${encodeURIComponent(me.id)}`;
const seg = (id: string) => encodeURIComponent(id);

/** The JSON body as a plain object; anything else (missing, an array, not JSON) reads as `{}`. */
export async function objectBody(request: Request): Promise<Record<string, unknown>> {
  const body: unknown = await request.json().catch(() => null);
  return body && typeof body === "object" && !Array.isArray(body) ? (body as Record<string, unknown>) : {};
}

// --- The Wall (S-WALL, L-WALL): anyone signed in ---------------------------------------------------------------

/** Query values the Wall takes, checked before they reach the worker (the worker checks them again). */
export function wallQuery(
  params: URLSearchParams,
  keys: readonly ("kind" | "sort" | "limit" | "offset" | "order")[],
): URLSearchParams | NextResponse {
  const out = new URLSearchParams();
  for (const key of keys) {
    const value = params.get(key);
    if (value === null || value === "") continue;
    const ok =
      key === "kind"
        ? value === "all" || isEnumValue("kind", value)
        : key === "sort"
          ? isEnumValue("wall_sort", value)
          : key === "order"
            ? value === "wall" || value === "leaderboard"
            : /^[0-9]{1,4}$/.test(value);
    if (!ok) {
      const code = key === "limit" || key === "offset" ? "bad_page" : `bad_${key}`;
      return packError(400, code, "", key);
    }
    out.set(key, value);
  }
  return out;
}

const withQuery = (path: string, q: URLSearchParams) => (q.toString() ? `${path}?${q.toString()}` : path);

export const kindling = (q: URLSearchParams) => relay(withQuery("/internal/wall/kindling", q));
export const justIn = (q: URLSearchParams) => relay(withQuery("/internal/wall/just-in", q));
export const wallOnes = (q: URLSearchParams) => relay(withQuery("/internal/wall/ones", q));
export const wallImpact = () => relay("/internal/wall/impact");
export const wallEmber = () => relay("/internal/wall/ember");

// --- The Ones' posts (Home's fan, C-ONES-FAN): anyone signed in -------------------------------------------------

export const onesPosts = (me: CurrentUser) => relay(`/internal/ones/posts?${as(me)}`);

export const likePost = (me: CurrentUser, postId: string, body: Record<string, unknown>) =>
  relay(`/internal/ones/posts/${seg(postId)}/like?${as(me)}`, {
    method: "PUT",
    body: { liked: body.liked },
    failMessage: SAVE_FAILED,
  });

// --- A One's own dashboard (S-ONE): the worker serves the One alone (403 `not_a_one` for anyone else) ------------

export const oneDashboard = (me: CurrentUser) => relay(`/internal/one?${as(me)}`);

export const oneNumber = (me: CurrentUser, body: Record<string, unknown>) =>
  relay(`/internal/one/number?${as(me)}`, {
    method: "PUT",
    body: { number: body.number },
    failMessage: SAVE_FAILED,
    field: "number",
  });

export const oneBrief = (me: CurrentUser, body: Record<string, unknown>) =>
  relay(`/internal/one/brief?${as(me)}`, {
    method: "POST",
    body: { text: body.text },
    failMessage: SAVE_FAILED,
    field: "text",
  });

export const glowUpSeen = (me: CurrentUser, glowId: string) =>
  relay(`/internal/one/glow-up/${seg(glowId)}/seen?${as(me)}`, { method: "POST" });

// --- Profile and settings (S-H6, A-API.me): the signed-in person's own, always ----------------------------------

export const profile = (me: CurrentUser) => relay(`/internal/me/profile?${as(me)}`);

/**
 * Saves the switches in the body at once and returns every switch's new state (S-H6.rules/1). A save that fails
 * for any reason answers with "Couldn't save that. Try again." and names the switch when there was one, so the
 * screen flips it back.
 */
export const saveSettings = (me: CurrentUser, body: Record<string, unknown>) => {
  const keys = Object.keys(body);
  return relay(`/internal/me/settings?${as(me)}`, {
    method: "PATCH",
    body,
    failMessage: SAVE_FAILED,
    field: keys.length === 1 ? keys[0] : undefined,
  });
};
