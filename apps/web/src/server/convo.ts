/**
 * An idea's conversation (L-CONVO; A-API.inbox: `GET /ideas/:id/conversation`, `POST …/messages`, and removing
 * one's own message). Each route handler checks the session, then forwards to the worker's `/internal/*` route
 * with the signed-in person as `user_id`. The worker decides who may read or write on this idea, answering anyone
 * else 404, and replies in the pack's error shape `{ error: { code, message, field? } }`, passed through as it is
 * so a message shows under its field.
 *
 * Live updates: nothing is sent on `A-API.events` yet; S-08 refetches after each action (BLD-F050).
 */
import { NextResponse, type NextRequest } from "next/server";

import type { ConversationMessageCreate, ConversationView } from "@/lib/contracts";
import { signedIn } from "@/server/auth/authorize";
import type { CurrentUser } from "@/server/auth/current";
import { workerFetch } from "@/server/worker";

type Ctx = { params: Promise<{ id?: string; entryId?: string }> };

const enc = encodeURIComponent;

function base(id: string): string {
  return `/internal/ideas/${enc(id)}/conversation`;
}

function withUser(path: string, me: CurrentUser): string {
  return `${path}?${new URLSearchParams({ user_id: me.id }).toString()}`;
}

async function forward(path: string, init: RequestInit = {}): Promise<NextResponse> {
  const res = await workerFetch(path, init);
  const text = await res.text();
  const json = text ? (JSON.parse(text) as unknown) : null;
  return NextResponse.json(json, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

/** Only the fields the worker reads, each of the right type; anything else is dropped. */
export function messageBody(raw: unknown): ConversationMessageCreate {
  const r = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const ids = (v: unknown): string[] | undefined =>
    Array.isArray(v) ? v.filter((x): x is string => typeof x === "string").slice(0, 20) : undefined;
  const out: ConversationMessageCreate = { text: typeof r.text === "string" ? r.text : "" };
  const files = ids(r.file_ids);
  const mentions = ids(r.mentions);
  if (files) out.file_ids = files;
  if (mentions) out.mentions = mentions;
  return out;
}

/** `GET /api/ideas/:id/conversation` → `ConversationView`. */
export async function getConversation(_request: NextRequest, ctx: Ctx): Promise<NextResponse> {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return forward(withUser(base((await ctx.params).id ?? ""), me));
}

/** `POST /api/ideas/:id/conversation/messages` `{ text, file_ids?, mentions? }` → `{ entry, hidden }`. */
export async function postMessage(request: NextRequest, ctx: Ctx): Promise<NextResponse> {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const raw: unknown = await request.json().catch(() => ({}));
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const key = request.headers.get("Idempotency-Key");
  if (key) headers["Idempotency-Key"] = key;
  return forward(withUser(`${base((await ctx.params).id ?? "")}/messages`, me), {
    method: "POST",
    headers,
    body: JSON.stringify(messageBody(raw)),
  });
}

/** `DELETE /api/ideas/:id/conversation/messages/:entryId`: the sender's own message, within 5 minutes. */
export async function deleteMessage(_request: NextRequest, ctx: Ctx): Promise<NextResponse> {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const { id = "", entryId = "" } = await ctx.params;
  return forward(withUser(`${base(id)}/messages/${enc(entryId)}`, me), { method: "DELETE" });
}

/** For S-08's server component: the conversation, or null when this person may not read it. */
export async function readConversation(me: CurrentUser, id: string): Promise<ConversationView | null> {
  const res = await workerFetch(withUser(base(id), me));
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`worker answered ${res.status}`);
  return (await res.json()) as ConversationView;
}
