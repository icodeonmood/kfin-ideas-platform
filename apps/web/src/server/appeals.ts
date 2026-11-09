/** Appeals (§4.12) and the fairness and calibration reports (§3.8, §5.4). The worker checks who may file, who sits
 * on the panel and who chairs it; reports carry counts only, with small numbers suppressed. */
import type { CurrentUser } from "./auth/current";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

const APL = /^APL-[0-9]{4}-[0-9]{4}$/;

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await workerFetch(path, { signal: AbortSignal.timeout(60_000), ...init });
  const out = (await res.json().catch(() => ({ error: "unavailable" }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(out.error ?? "unavailable"));
  return out as T;
}
const post = (body: Record<string, unknown>) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const myAppeals = (me: CurrentUser) =>
  call<{ decisions: unknown[]; panel: unknown[] }>(`/internal/appeals?user_id=${me.id}`);
export const fileAppeal = (me: CurrentUser, body: Record<string, unknown>) =>
  call<Record<string, unknown>>(`/internal/appeals`, post({ ...body, user_id: me.id }));
export const appealView = (me: CurrentUser, id: string) => {
  if (!APL.test(id)) throw new SubmissionError(404, "not_found");
  return call<Record<string, unknown>>(`/internal/appeals/${id}?user_id=${me.id}`);
};
export const decideAppeal = (me: CurrentUser, id: string, body: Record<string, unknown>) => {
  if (!APL.test(id)) throw new SubmissionError(404, "not_found");
  return call<Record<string, unknown>>(`/internal/appeals/${id}/decision`, post({ ...body, user_id: me.id }));
};
export const report = (me: CurrentUser, kind: "fairness" | "calibration", quarter?: string) => {
  const q = new URLSearchParams({ user_id: me.id });
  if (quarter && /^\d{4}-Q[1-4]$/.test(quarter)) q.set("quarter", quarter);
  return call<Record<string, unknown>>(`/internal/reports/${kind}?${q.toString()}`);
};
