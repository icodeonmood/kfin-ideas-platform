/** Private points (DEC-078, BLD-130) and a person's own lens (BLD-135), web side: only ever the signed-in
 * person's own. */
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

/** Your own lens (BLD-135): your ideas by plain stage group and the groups you are part of. Counts only. */
export type MyLens = {
  ideas: Record<string, number>;
  shared: number;
  groups: {
    id: string;
    area: string | null;
    stage: string;
    ideas: number;
    colleagues: number;
    how: string;
  }[];
  teamed_up: number;
};

export async function myLens(me: CurrentUser): Promise<MyLens> {
  const res = await workerFetch(`/internal/me/${me.id}/lens`, { signal: AbortSignal.timeout(15_000) });
  const out = (await res.json().catch(() => ({ error: "lens_unavailable" }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(out.error ?? "lens_unavailable"));
  return out as MyLens;
}
