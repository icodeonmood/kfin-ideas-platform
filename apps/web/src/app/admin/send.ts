/** One call from the admin page, with the pack's error shape read back (A-API.conventions/2). */
export type Problem = { code: string; message: string; field?: string };

export async function send(
  method: "POST" | "PUT" | "DELETE",
  url: string,
  body: Record<string, unknown> = {},
): Promise<{ ok: true; json: Record<string, unknown> } | { ok: false; problem: Problem }> {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (res.ok) return { ok: true, json };
  const err = json.error;
  if (err && typeof err === "object") {
    const e = err as Problem;
    return { ok: false, problem: { code: e.code, message: e.message || FALLBACK, field: e.field } };
  }
  return { ok: false, problem: { code: typeof err === "string" ? err : "error", message: FALLBACK } };
}

export const FALLBACK = "That didn't work. Check the details and try again.";
