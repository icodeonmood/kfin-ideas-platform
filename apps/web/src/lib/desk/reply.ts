/**
 * What the review side's screens show when a call fails. The worker answers in the pack's error shape,
 * `{ error: { code, message, field? } }` (A-API.conventions/2). The web's own gates answer with a bare code instead:
 * the kill-switch check `{ error: "paused", switch, banner }` with 503 (§7.6, non-negotiable 9), and sign-in or role
 * checks `{ error: "forbidden" }` with 401 or 403. Those carry no words for a person, so the screen shows the paused
 * feature's banner, or F-COPY's failure line, never the code.
 */
import { BANNERS, type SwitchName } from "@/lib/killswitch-routes";

export const TRY_AGAIN = "That didn’t go through. Try again.";

export type ApiError = {
  code: string;
  message: string;
  field?: string;
  words?: string[];
  suggestions?: { word: string; suggestion: string }[];
};

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** The error in a reply's body, in the pack's shape; null when the body carries none. */
export function replyError(json: unknown): ApiError | null {
  if (!isRecord(json) || json.error === undefined || json.error === null) return null;
  const e = json.error;
  if (typeof e === "string") {
    const named = typeof json.switch === "string" ? BANNERS[json.switch as SwitchName] : undefined;
    const banner = typeof json.banner === "string" && json.banner ? json.banner : undefined;
    return { code: e, message: named ?? banner ?? TRY_AGAIN };
  }
  if (isRecord(e) && typeof e.message === "string" && e.message) {
    return { ...(e as ApiError), code: typeof e.code === "string" ? e.code : "failed" };
  }
  return { code: "failed", message: TRY_AGAIN };
}

/** A JSON call from a review screen: the body on success, else the error to show. Never throws. */
export async function call<T>(
  url: string,
  init: { method?: "GET" | "POST" | "PUT"; body?: unknown } = {},
): Promise<{ ok: true; body: T } | { ok: false; error: ApiError; status: number }> {
  let res: Response;
  try {
    res = await fetch(url, {
      method: init.method ?? "GET",
      headers: init.body === undefined ? undefined : { "Content-Type": "application/json" },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    return { ok: false, error: { code: "failed", message: TRY_AGAIN }, status: 0 };
  }
  const json: unknown = await res.json().catch(() => null);
  const error = replyError(json);
  if (!res.ok || error) {
    return { ok: false, error: error ?? { code: "failed", message: TRY_AGAIN }, status: res.status };
  }
  return { ok: true, body: json as T };
}
