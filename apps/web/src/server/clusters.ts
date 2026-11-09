/**
 * Weekly clustering for the review desk (§4.4 B): the latest runs, "run now", one proposal's screen and the desk's
 * actions on it. The worker does the work; this checks who may ask and chooses the restore mode (§3.1).
 */
import { can } from "@/lib/rbac";

import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";
import { restoreMode } from "./restore";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

export type ClusterRun = {
  id: string;
  state: string;
  pool_size: number | null;
  counts: Record<string, number>;
  started_at: string;
  finished_at: string | null;
};

export type ProposalIdea = {
  idea_id: string;
  one_line?: string | null;
  stage?: string;
  lobs?: string[];
  areas?: string[];
  contributor?: string;
  cluster_id?: string | null;
  missing?: boolean;
};

export type ProposalView = {
  id: number;
  proposal_id: number;
  run_id: string;
  kind: "new" | "grow" | "merge" | "split";
  kind_words: string;
  state: string;
  item_state: string;
  targets: { id: string; title: string | null; member_count: number; state: string }[];
  members: ProposalIdea[];
  dropped: (ProposalIdea & { reason: string | null; removed_by: string | null; code: string | null })[];
  split_groups: string[][] | null;
  summary: {
    name?: string;
    description?: string;
    problem?: string;
    variations?: { member: string; note: string }[];
    solution?: { text: string; credit: string[] }[];
    lobs?: string[];
    roles_affected?: string[];
    open_questions?: string[];
  } | null;
  refs: Record<string, string>;
  generated_by: string | null;
  metrics: Record<string, number>;
  checks_skipped: string[];
  due_at: string | null;
  decided_by: string | null;
  decided_at: string | null;
  cluster_id: string | null;
  final: Record<string, unknown> | null;
  mode: "real" | "neutral";
  may_act: boolean;
};

const ID = /^[0-9]{1,12}$/;

export async function runs(): Promise<ClusterRun[]> {
  const res = await workerFetch("/internal/cluster-runs");
  if (!res.ok) throw new SubmissionError(502, "runs_unavailable");
  return (await res.json()) as ClusterRun[];
}

export async function runNow(me: CurrentUser) {
  const res = await workerFetch("/internal/cluster-runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: me.id }),
  });
  const out = (await res.json().catch(() => ({ error: "run_failed" }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(out.error ?? "run_failed"));
  return out;
}

/** The desk handling the proposal and the core committee see real values; anyone else neutral labels. */
export async function proposalView(me: CurrentUser, id: string): Promise<ProposalView> {
  if (!ID.test(id)) throw new SubmissionError(404, "not_found");
  const row = await getDb()
    .selectFrom("review_items")
    .select(["assigned_to", "state", "item_type"])
    .where("id", "=", id)
    .executeTakeFirst();
  if (!row || row.item_type !== "cluster_proposal") throw new SubmissionError(404, "not_found");
  const mode = restoreMode(
    { id: me.id, contributorCode: null, roles: [...me.roles] },
    { contributorCode: "", reviewItem: { assignedTo: row.assigned_to, state: row.state } },
  );
  const res = await workerFetch(`/internal/cluster-proposals/${id}/view?mode=${mode}`);
  if (!res.ok) throw new SubmissionError(res.status === 404 ? 404 : 502, "item_unavailable");
  const body = (await res.json()) as Omit<ProposalView, "mode" | "may_act">;
  return { ...body, mode, may_act: can(me.roles, "approve_cluster_proposals") };
}

const ACTIONS = ["approve", "reject", "remove_member"] as const;

export async function act(me: CurrentUser, id: string, input: unknown) {
  if (!ID.test(id)) throw new SubmissionError(404, "not_found");
  if (!can(me.roles, "approve_cluster_proposals")) throw new SubmissionError(403, "forbidden");
  const body = (input ?? {}) as Record<string, unknown>;
  const action = ACTIONS.find((a) => a === body.action);
  if (!action) throw new SubmissionError(400, "action_required");
  const pick = (k: string, max: number) =>
    typeof body[k] === "string" ? (body[k] as string).slice(0, max) : undefined;
  const res = await workerFetch(`/internal/cluster-proposals/${id}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action,
      name: pick("name", 200),
      description: pick("description", 400),
      problem: pick("problem", 3000),
      reason_code: pick("reason_code", 40),
      note: pick("note", 2000),
      idea_id: pick("idea_id", 20),
      reviewer_user_id: me.id,
    }),
    signal: AbortSignal.timeout(30_000),
  });
  const out = (await res.json().catch(() => ({ error: "action_failed" }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(out.error ?? "action_failed"));
  return out;
}

export type WorkingGroupItem = {
  id: number;
  cluster_id: string;
  contributors: number;
  lobs: string[];
  state: string;
  created_at: string;
};

/** A "Form a working group" item from the trigger (§4.4 B step 9): counts and LOBs only, no names. */
export async function workingGroupItem(id: string): Promise<WorkingGroupItem> {
  if (!ID.test(id)) throw new SubmissionError(404, "not_found");
  const row = await getDb()
    .selectFrom("review_items")
    .select(["id", "ref_id", "proposal", "state", "created_at", "item_type"])
    .where("id", "=", id)
    .executeTakeFirst();
  if (!row || row.item_type !== "working_group_trigger") throw new SubmissionError(404, "not_found");
  const p = (row.proposal ?? {}) as { contributors?: string[]; lobs?: string[] };
  return {
    id: Number(row.id),
    cluster_id: row.ref_id,
    contributors: (p.contributors ?? []).length,
    lobs: p.lobs ?? [],
    state: row.state,
    created_at: new Date(row.created_at).toISOString(),
  };
}
