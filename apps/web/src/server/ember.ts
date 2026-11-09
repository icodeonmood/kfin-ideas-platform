/**
 * The Ember (DEC-062, DEC-070, BLD-128), web side. The worker builds every issue from what everyone may see and
 * re-checks the person's live grants; this module passes who is acting and turns refusals into codes.
 */
import type { CurrentUser } from "./auth/current";
import type { Measures } from "./ones";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

export type EmberOne = {
  number: number;
  name: string | null;
  tier: number;
  tier_name: string;
  tier_colour: string;
  founding: boolean;
  line: string | null;
  brief: string | null;
  measures: Measures;
};

export type EmberIssue = {
  id: number;
  state: "draft" | "sent";
  month: string;
  month_label: string;
  sent_at?: string;
  note: string | null;
  can_send?: boolean;
  ember_paused?: boolean;
  ones_paused: boolean;
  impact: EmberOne[];
  new_ones: EmberOne[];
  shipped: { label: string; words: string }[];
  results: { label: string; mark: string; measures: Measures }[];
  by_lob: { lob: string; shared: number; picked: number }[];
  managers: string[];
  coming_soon: string[];
};

export type EmberArchive = { issues: { id: number; month_label: string; sent_at: string }[] };

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await workerFetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    signal: AbortSignal.timeout(30_000),
  });
  const out = (await res.json().catch(() => ({ error: "ember_unavailable" }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(out.error ?? "ember_unavailable"));
  return out as T;
}

const idOf = (value: string) => {
  if (!/^\d{1,12}$/.test(value)) throw new SubmissionError(404, "not_found");
  return value;
};

export const emberArchive = () => call<EmberArchive>("/internal/ember");

export const emberIssue = (me: CurrentUser, id: string) =>
  call<EmberIssue>(`/internal/ember/${idOf(id)}/${me.id}`);

export const emberCurrent = (me: CurrentUser) =>
  call<{ id: number | null }>(`/internal/ember/current/${me.id}`);

export const emberDraft = (me: CurrentUser, body: Record<string, unknown>) =>
  call<{ id: number; created: boolean }>("/internal/ember/drafts", {
    method: "POST",
    body: JSON.stringify({ month: body.month ?? "", actor_user_id: me.id }),
  });

export const emberNote = (me: CurrentUser, id: string, body: Record<string, unknown>) =>
  call<{ id: number }>(`/internal/ember/${idOf(id)}/note`, {
    method: "PUT",
    body: JSON.stringify({ note: body.note ?? "", actor_user_id: me.id }),
  });

export const emberSend = (me: CurrentUser, id: string) =>
  call<{ id: number; state: string }>(`/internal/ember/${idOf(id)}/send`, {
    method: "POST",
    body: JSON.stringify({ actor_user_id: me.id }),
  });
