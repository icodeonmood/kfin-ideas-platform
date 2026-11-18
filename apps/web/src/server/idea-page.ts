/**
 * Lane E's API for an idea's own pages (A-API.ideas, A-API.my-ideas): `/ideas/:id` (S-06 for the sharer, S-09 for
 * anyone else), My ideas (S-07), withdraw and restore (L-SUBMIT.withdraw). Each route handler checks the session
 * and the capability, then forwards to the worker's `/internal/*` route (services/worker/ideapage/routes.py) with
 * the signed-in person's id. The person is never taken from the request. The worker decides what that person may
 * see of this idea and answers in the pack's error shape, `{ error: { code, message } }`, passed through as it is.
 *
 * Defence in depth (DEC-104, P-PRODUCT.privacy, non-negotiable 7): whatever the worker sends, the sharer's page
 * (S-06) leaves only when it names the signed-in person as its sharer, a colleague's view (S-09) leaves with the
 * public fields only, a withdrawn idea's S-09 with its reference and one line (BLD-E011), and a redirect carries
 * nothing but where to go. Nothing here logs a body (non-negotiable 3).
 */
import { NextResponse, type NextRequest } from "next/server";

import { authorize, signedIn } from "@/server/auth/authorize";
import type { CurrentUser } from "@/server/auth/current";
import { SEARCH_MAX, withoutSearch } from "@/lib/search-memory";
import { readJson } from "@/server/http";
import { workerFetch } from "@/server/worker";

const NO_STORE = { "Cache-Control": "no-store" };
const NOT_FOUND = { error: { code: "not_found", message: "We can’t find that idea." } };
const UNAVAILABLE = {
  error: { code: "unavailable", message: "This page can’t be loaded right now. Try again in a minute." },
};

/** S-09 may carry these idea fields and no others (S-09.rules/1): the short summary, never raw words. */
export const COLLEAGUE_IDEA_FIELDS = [
  "id",
  "ref",
  "status",
  "kind",
  "title",
  "summary",
  "often",
  "affects",
  "brings",
  "area",
  "city",
  "sharer",
  "credited",
  "shared_at",
  "stages",
  "crew",
  "linked_similar_count",
  "wall",
  "merged_into",
  "next_step",
] as const;
const COLLEAGUE_PAGE_FIELDS = [
  "state",
  "back",
  "pill",
  "shared_line",
  "summary_heading",
  "summary_note",
  "about",
  "team_up",
] as const;

type Json = Record<string, unknown>;

function pick(obj: unknown, keys: readonly string[]): Json {
  const out: Json = {};
  if (!obj || typeof obj !== "object") return out;
  for (const k of keys) if (k in obj) out[k] = (obj as Json)[k];
  return out;
}

/** A withdrawn idea's S-09 (BLD-E011): the reference and one line, no title, summary, crew, track or name. */
const WITHDRAWN_IDEA_FIELDS = ["id", "ref", "status"] as const;
const WITHDRAWN_PAGE_FIELDS = ["state", "back", "pill"] as const;
const WITHDRAWN_TEAM_UP_FIELDS = ["state", "line", "can_team_up"] as const;

function isWithdrawn(v: Json): boolean {
  const idea = v.idea as Json | undefined;
  const page = v.page as Json | undefined;
  return idea?.status === "withdrawn" || page?.state === "withdrawn";
}

/** S-06 is the sharer's alone: it leaves only when the page names the signed-in person as its sharer. */
function isMine(v: Json, me: CurrentUser): boolean {
  const sharer = (v.idea as Json | undefined)?.sharer as Json | null | undefined;
  return typeof sharer?.id === "string" && sharer.id === me.id;
}

/** The view as it may leave the web app: the sharer's page whole, to its sharer only; S-09 and the redirects cut
 * to their fields; anything else is "not found". */
export function guardView(body: unknown, me: CurrentUser): unknown {
  if (!body || typeof body !== "object" || "error" in body) return body;
  const v = body as Json;
  if (v.view === "sharer") return isMine(v, me) ? v : NOT_FOUND;
  if (v.view === "colleague" && isWithdrawn(v)) {
    const page = (v.page ?? {}) as Json;
    return {
      view: "colleague",
      screen: "S-09",
      idea: { ...pick(v.idea, WITHDRAWN_IDEA_FIELDS), status: "withdrawn" },
      page: {
        ...pick(page, WITHDRAWN_PAGE_FIELDS),
        state: "withdrawn",
        team_up: pick(page.team_up, WITHDRAWN_TEAM_UP_FIELDS),
      },
    };
  }
  if (v.view === "colleague") {
    return {
      view: "colleague",
      screen: "S-09",
      idea: pick(v.idea, COLLEAGUE_IDEA_FIELDS),
      page: pick(v.page, COLLEAGUE_PAGE_FIELDS),
    };
  }
  if (v.view === "desk" || v.view === "draft") return { view: v.view, to: v.to };
  return NOT_FOUND;
}

/** Withdraw and restore answer with the sharer's page (`SharerView`), and only to its sharer. */
export function guardSharer(body: unknown, me: CurrentUser): unknown {
  if (!body || typeof body !== "object" || "error" in body) return body;
  const v = body as Json;
  return v.view === "sharer" && isMine(v, me) ? v : NOT_FOUND;
}

function workerPath(
  base: string,
  me: CurrentUser,
  query: Record<string, string | null | undefined> = {},
): string {
  const qs = new URLSearchParams({ user_id: me.id });
  for (const [k, v] of Object.entries(query)) if (v) qs.set(k, v);
  return `${base}?${qs.toString()}`;
}

async function forward(path: string, init: RequestInit = {}, shape?: (body: unknown) => unknown) {
  let res: Response;
  try {
    res = await workerFetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    });
  } catch {
    return NextResponse.json(UNAVAILABLE, { status: 503, headers: NO_STORE });
  }
  const text = await res.text();
  let json: unknown = null;
  try {
    json = text ? (JSON.parse(text) as unknown) : null;
  } catch {
    return NextResponse.json(UNAVAILABLE, { status: 502, headers: NO_STORE });
  }
  const body = res.ok && shape ? shape(json) : json;
  const status = body && typeof body === "object" && "error" in body && res.ok ? 404 : res.status;
  return NextResponse.json(body, { status, headers: NO_STORE });
}

const REF = /^(IDEA-[0-9]{4}-[0-9]{6}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/;

async function ideaKey(ctx: { params: Promise<{ id?: string }> }): Promise<string | null> {
  const id = (await ctx.params).id ?? "";
  return REF.test(id) ? id : null;
}

/** An opaque per-device id the client keeps, for "on this laptop" (S-07.layout/4); never a person's detail. */
function deviceId(request: NextRequest): string | null {
  const d = request.headers.get("x-device-id");
  return d && /^[A-Za-z0-9_-]{8,64}$/.test(d) ? d : null;
}

/** GET /api/ideas/:id — `IdeaViewResponse` (lib/contracts/api.ts). Query: `from`, `back` (P-ROUTES.state). A list's
 * address never holds a search (DEC-110); a `q` in `back` all the same (an older link) is dropped before it goes on. */
export async function getIdeaView(request: NextRequest, ctx: { params: Promise<{ id?: string }> }) {
  const me = await authorize("see_org_ideas");
  if (me instanceof NextResponse) return me;
  const key = await ideaKey(ctx);
  if (!key) return NextResponse.json(NOT_FOUND, { status: 404, headers: NO_STORE });
  const q = request.nextUrl.searchParams;
  return forward(
    workerPath(`/internal/ideas/${encodeURIComponent(key)}/view`, me, {
      came_from: q.get("from")?.slice(0, 40),
      back: backWithoutSearch(q.get("back")),
    }),
    {},
    (body) => guardView(body, me),
  );
}

/** `back` as the worker gets it: at most 600 characters of a path, without a search. */
export function backWithoutSearch(back: string | null | undefined): string | undefined {
  return back ? withoutSearch(back.slice(0, 600)) : undefined;
}

/** My ideas' list keys an address may hold (P-ROUTES.state). The search is not one (DEC-110). */
const MY_IDEAS_KEYS = ["list", "filter", "sort", "row"] as const;

/** GET /api/me/ideas — `MyIdeasResponse` (lib/contracts/api.ts). Query: `list`, `filter`, `sort`, `row` (S-07.return).
 * A `q` in the query is never read or passed on: a search is asked for with POST (DEC-110). */
export async function getMyIdeas(request: NextRequest) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const q = request.nextUrl.searchParams;
  const query: Record<string, string | null | undefined> = { device: deviceId(request) };
  for (const k of MY_IDEAS_KEYS) query[k] = q.get(k)?.slice(0, 200);
  return forward(workerPath(`/internal/me/${encodeURIComponent(me.id)}/my-ideas`, me, query));
}

/** POST /api/me/ideas `MyIdeasQuery` — the same read with the search (DEC-110): the words travel in this body and in
 * the worker's, never in a URL. Each value is a string of at most 200 characters; anything else is left out. */
export async function postMyIdeas(request: NextRequest) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const raw = await readJson(request);
  const body: Record<string, string> = {};
  for (const k of [...MY_IDEAS_KEYS, "q"] as const) {
    const v = raw[k];
    if (typeof v === "string" && v) body[k] = v.slice(0, k === "q" ? SEARCH_MAX : 200);
  }
  const device = deviceId(request);
  if (device) body.device = device;
  return forward(workerPath(`/internal/me/${encodeURIComponent(me.id)}/my-ideas`, me), {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** POST /api/ideas/:id/withdraw `{ reason? }` and POST /api/ideas/:id/restore — the sharer's page (`SharerView`). */
export function postIdeaAction(action: "withdraw" | "restore") {
  return async (request: NextRequest, ctx: { params: Promise<{ id?: string }> }) => {
    const me = await authorize("submit");
    if (me instanceof NextResponse) return me;
    const key = await ideaKey(ctx);
    if (!key) return NextResponse.json(NOT_FOUND, { status: 404, headers: NO_STORE });
    const body: Json = {};
    if (action === "withdraw") {
      const raw = await readJson(request);
      if (typeof raw.reason === "string") body.reason = raw.reason.slice(0, 2000);
    }
    return forward(
      workerPath(`/internal/ideas/${encodeURIComponent(key)}/${action}`, me),
      { method: "POST", body: JSON.stringify(body) },
      (out) => guardSharer(out, me),
    );
  };
}
