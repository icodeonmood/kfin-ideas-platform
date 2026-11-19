/**
 * Listen in Sarvam's voice (DEC-108 (4), L-LISTEN, C-LISTEN; BLD-C114), web side. The worker reads lane B's masked
 * script, makes the audio part by part and caches it with its chapters; the web app checks the capability and passes the
 * audio through as it comes. The on-device voice stays the player's fallback when this answers anything but audio.
 * `view_review_queue` also lets admins in, so the signed-in person goes to the worker as `user_id` and the worker
 * refuses anyone not on the review desk or the Ones Committee (P-PRODUCT.privacy, DEC-104; BLD-C198).
 */
import { workerFetch } from "./worker";

const REF = /^(?:IDEA-[0-9]{4}-[0-9]{6}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/;

export const isIdeaRef = (v: string): boolean => REF.test(v);

const at = (ref: string, userId: string, tail = ""): string =>
  `/internal/listen/${encodeURIComponent(ref)}${tail}?${new URLSearchParams({ user_id: userId }).toString()}`;

export async function listenAudio(ref: string, userId: string, range: string | null): Promise<Response> {
  const res = await workerFetch(at(ref, userId), {
    headers: range ? { Range: range } : {},
    signal: AbortSignal.timeout(180_000), // the first listen streams while Sarvam makes the six parts
  });
  if (!res.ok || !(res.headers.get("content-type") ?? "").startsWith("audio/")) {
    const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    if (res.status === 416) return new Response(null, { status: 416, headers: pick(res, ["content-range"]) });
    return Response.json({ error: String(body.error ?? "listen_unavailable") }, { status: res.status });
  }
  return new Response(res.body, {
    status: res.status,
    headers: pick(res, ["content-type", "content-length", "content-range", "accept-ranges", "cache-control"]),
  });
}

export async function listenChapters(ref: string, userId: string): Promise<Response> {
  const res = await workerFetch(at(ref, userId, "/chapters"));
  const body = (await res.json().catch(() => ({ error: "listen_unavailable" }))) as Record<string, unknown>;
  return Response.json(body, { status: res.status, headers: { "Cache-Control": "private, no-store" } });
}

function pick(res: Response, names: string[]): Headers {
  const out = new Headers();
  for (const n of names) {
    const v = res.headers.get(n);
    if (v !== null) out.set(n, v);
  }
  return out;
}
