/**
 * The committee flow (§4.5–§4.7) from the web side. The worker does every read and write: it keeps sealed
 * scores and assessments sealed, serves blind views and checks the chair, the roster and conflicts of interest.
 * This passes who is asking, after the proxy has checked the capability for the route (policy/rbac.yaml).
 */
import type { CurrentUser } from "./auth/current";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

const ROUND = /^RND-[0-9]{4}-[0-9]{4}$/;
const PRES = /^PRS-[0-9]{4}-[0-9]{4}$/;
const ITEM = /^[0-9]{1,12}$/;
const WG = /^WG-[0-9]{4}$/;

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

const only = (re: RegExp, id: string) => {
  if (!re.test(id)) throw new SubmissionError(404, "not_found");
  return id;
};

// ---- rounds (§4.6) -----------------------------------------------------------------------------------------------
export const rounds = (me: CurrentUser) =>
  call<{ rounds: unknown[]; chair: boolean; presentations: unknown[] }>(
    `/internal/committee/rounds?user_id=${me.id}`,
  );
export const roundView = (me: CurrentUser, id: string) =>
  call<Record<string, unknown>>(`/internal/committee/rounds/${only(ROUND, id)}?user_id=${me.id}`);
export const roundAct = (me: CurrentUser, id: string, body: Record<string, unknown>) =>
  call<Record<string, unknown>>(
    `/internal/committee/rounds/${only(ROUND, id)}/action`,
    post({ ...body, user_id: me.id }),
  );
export const openCycle = (me: CurrentUser, body: Record<string, unknown>) =>
  call<Record<string, unknown>>(`/internal/committee/cycles`, post({ ...body, user_id: me.id }));

// ---- presentations and decisions (§4.7) --------------------------------------------------------------------------
export const presentationForCommittee = (me: CurrentUser, id: string) =>
  call<Record<string, unknown>>(`/internal/committee/presentations/${only(PRES, id)}?user_id=${me.id}`);
export const presentationCommitteeAct = (me: CurrentUser, id: string, body: Record<string, unknown>) =>
  call<Record<string, unknown>>(
    `/internal/committee/presentations/${only(PRES, id)}/action`,
    post({ ...body, user_id: me.id }),
  );
export const presentationForContributor = (me: CurrentUser, id: string) =>
  call<Record<string, unknown>>(`/internal/presentations/${only(PRES, id)}?user_id=${me.id}`);
export const presentationContributorAct = (me: CurrentUser, id: string, body: Record<string, unknown>) =>
  call<Record<string, unknown>>(
    `/internal/presentations/${only(PRES, id)}/action`,
    post({ ...body, user_id: me.id }),
  );

// ---- qualify (§4.5) and working groups -----------------------------------------------------------------------------
export const qualifyView = (me: CurrentUser, id: string) =>
  call<Record<string, unknown>>(`/internal/qualify/${only(ITEM, id)}?user_id=${me.id}`);
export const qualifyAct = (me: CurrentUser, id: string, body: Record<string, unknown>) =>
  call<Record<string, unknown>>(
    `/internal/qualify/${only(ITEM, id)}/action`,
    post({ ...body, reviewer_user_id: me.id }),
  );
export const workingGroup = (me: CurrentUser, id: string) =>
  call<Record<string, unknown>>(`/internal/working-groups/${only(WG, id)}?user_id=${me.id}`);
