/** Private points (DEC-078, BLD-130), web side: only ever the signed-in person's own. */
import type { CurrentUser } from "./auth/current";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

export type MyPoints = {
  total: number;
  last_12_months: number;
  recent: { what: string; points: number; on: string }[];
  coming_soon: string[];
};

export async function myPoints(me: CurrentUser): Promise<MyPoints> {
  const res = await workerFetch(`/internal/me/${me.id}/points`, { signal: AbortSignal.timeout(15_000) });
  const out = (await res.json().catch(() => ({ error: "points_unavailable" }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(out.error ?? "points_unavailable"));
  return out as MyPoints;
}
