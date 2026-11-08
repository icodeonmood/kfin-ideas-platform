/**
 * The review console (§4.3, AT-B6-01/02). The queue is read here; the item screen and every action go through the
 * worker, which restores values and writes the transaction. The restore mode comes from `restoreMode` (§3.1).
 */
import { sql } from "kysely";

import { can } from "@/lib/rbac";

import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";
import { restoreMode } from "./restore";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

export type QueueFilters = {
  type?: string;
  kind?: string;
  lob?: string;
  category?: string;
  strength?: string;
  band?: string;
  age?: string;
};

export type QueueRow = {
  id: number;
  type: string;
  state: string;
  idea_id: string;
  kind: string | null;
  category: string | null;
  strength: number | null;
  summary: string | null;
  due_at: string | null;
  confidence: number | null;
  band: "low" | "medium" | "high" | null;
  age_days: number;
};

const OPEN = ["open", "in_progress", "awaiting_second_reviewer"];

function band(c: number | null): QueueRow["band"] {
  if (c === null) return null;
  return c < 0.5 ? "low" : c < 0.8 ? "medium" : "high";
}

/** Open items, soonest due first, then lowest confidence first (AT-B6-01). */
export async function queue(f: QueueFilters): Promise<QueueRow[]> {
  let q = getDb()
    .selectFrom("review_items as r")
    .leftJoin("ideas as i", "i.idea_id", "r.ref_id")
    .select([
      "r.id",
      "r.item_type",
      "r.state",
      "r.ref_id",
      "r.created_at",
      "r.proposal",
      "i.kind",
      "i.category",
      "i.strength",
      sql<string | null>`i.canvas->>'neutral_summary'`.as("summary"),
      sql<Date | null>`(SELECT t.due_at FROM sla_timers t WHERE t.entity_type = 'review_item'
        AND t.entity_id = r.id::text AND t.stage = 'review' ORDER BY t.id DESC LIMIT 1)`.as("due_at"),
      sql<number | null>`(SELECT min(value::numeric) FROM jsonb_each_text(r.confidence))`.as("confidence"),
    ])
    .where("r.state", "in", OPEN);
  if (f.type) q = q.where("r.item_type", "=", f.type);
  if (f.kind) q = q.where("i.kind", "=", f.kind);
  if (f.category) q = q.where("i.category", "=", f.category);
  if (f.strength && /^[0-5]$/.test(f.strength)) q = q.where("i.strength", ">=", Number(f.strength));
  if (f.lob && /^LOB-[a-z0-9-]+$/.test(f.lob))
    q = q.where(sql<boolean>`r.proposal->'system'->'lobs' ? ${f.lob}`);
  if (f.age && /^[0-9]{1,3}$/.test(f.age))
    q = q.where(sql<boolean>`r.created_at <= now() - make_interval(days => ${Number(f.age)})`);
  const rows = await q.execute();
  const out: QueueRow[] = rows.map((r) => ({
    id: Number(r.id),
    type: r.item_type,
    state: r.state,
    idea_id: r.ref_id,
    kind: r.kind ?? null,
    category: r.category ?? null,
    strength: r.strength ?? null,
    summary: r.summary,
    due_at: r.due_at ? new Date(r.due_at).toISOString() : null,
    confidence: r.confidence === null ? null : Number(r.confidence),
    band: band(r.confidence === null ? null : Number(r.confidence)),
    age_days: Math.floor((Date.now() - new Date(r.created_at).getTime()) / 86_400_000),
  }));
  const filtered = f.band ? out.filter((r) => r.band === f.band) : out;
  return filtered.sort((a, b) => {
    const da = a.due_at ?? "9999";
    const db = b.due_at ?? "9999";
    if (da !== db) return da < db ? -1 : 1;
    return (a.confidence ?? 2) - (b.confidence ?? 2);
  });
}

export async function itemView(me: CurrentUser, id: string) {
  if (!/^[0-9]{1,12}$/.test(id)) throw new SubmissionError(404, "not_found");
  const row = await getDb()
    .selectFrom("review_items as r")
    .innerJoin("ideas as i", "i.idea_id", "r.ref_id")
    .select(["r.assigned_to", "r.state", "i.contributor_code"])
    .where("r.id", "=", id)
    .executeTakeFirst();
  if (!row) throw new SubmissionError(404, "not_found");
  const mode = restoreMode(
    { id: me.id, contributorCode: me.contributorCode, roles: [...me.roles] },
    { contributorCode: row.contributor_code, reviewItem: { assignedTo: row.assigned_to, state: row.state } },
  );
  const res = await workerFetch(`/internal/review/items/${id}/view?mode=${mode}`);
  if (!res.ok) throw new SubmissionError(res.status === 404 ? 404 : 502, "item_unavailable");
  return { ...((await res.json()) as Record<string, unknown>), mode };
}

const ACTIONS = ["decide", "redirect", "ask", "visibility", "hold", "confirm_hold"] as const;

/** Who may act on an item: the desk, or a core committee member on an item they vetoed and now hold (§4.3). */
export async function mayAct(me: CurrentUser, id: string): Promise<boolean> {
  if (can(me.roles, "work_review_queue")) return true;
  if (!can(me.roles, "veto_desk_decision")) return false;
  const row = await getDb()
    .selectFrom("review_items")
    .select(["assigned_to", "vetoed_by"])
    .where("id", "=", id)
    .executeTakeFirst();
  return Boolean(row && row.assigned_to === me.id && row.vetoed_by === me.id);
}

export async function act(me: CurrentUser, id: string, input: unknown) {
  if (!/^[0-9]{1,12}$/.test(id)) throw new SubmissionError(404, "not_found");
  if (!(await mayAct(me, id))) throw new SubmissionError(403, "forbidden");
  const body = (input ?? {}) as Record<string, unknown>;
  const action = ACTIONS.find((a) => a === body.action);
  if (!action) throw new SubmissionError(400, "action_required");
  const path = action === "confirm_hold" ? "confirm-hold" : "action";
  const res = await workerFetch(`/internal/review/items/${id}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, reviewer_user_id: me.id }),
    signal: AbortSignal.timeout(30_000),
  });
  const out = (await res.json().catch(() => ({ error: "action_failed" }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(out.error ?? "action_failed"));
  return out;
}

export type DeskDecision = {
  item_id: number;
  idea_id: string;
  summary: string | null;
  stage: string;
  decision: Record<string, unknown> | null;
  decided_at: string;
  decided_by: string | null;
  note: string | null;
  vetoed: boolean;
  veto_open: boolean;
  veto_until: string | null;
};

export async function deskDecisions(): Promise<{
  decisions: DeskDecision[];
  disagreements: { item_id: number; idea_id: string; summary: string | null; at: string }[];
}> {
  const res = await workerFetch("/internal/review/desk-decisions");
  if (!res.ok) throw new SubmissionError(502, "desk_decisions_unavailable");
  return (await res.json()) as Awaited<ReturnType<typeof deskDecisions>>;
}

export async function vetoItem(me: CurrentUser, id: string, input: unknown) {
  if (!/^[0-9]{1,12}$/.test(id)) throw new SubmissionError(404, "not_found");
  const reason =
    typeof (input as { reason?: unknown })?.reason === "string" ? (input as { reason: string }).reason : "";
  const res = await workerFetch(`/internal/review/items/${id}/veto`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ member_user_id: me.id, reason: reason.slice(0, 2000) }),
  });
  const out = (await res.json().catch(() => ({ error: "veto_failed" }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(out.error ?? "veto_failed"));
  return out;
}

/** The submitter answers a question, or says "Disagree with this?" (§4.12 day one). */
export async function ideaWrite(
  me: CurrentUser,
  ideaUuid: string,
  kind: "answer" | "disagree",
  input: unknown,
) {
  if (!/^[0-9a-f-]{36}$/.test(ideaUuid) || !me.contributorCode) throw new SubmissionError(404, "not_found");
  const text =
    typeof (input as { text?: unknown })?.text === "string" ? (input as { text: string }).text : "";
  const res = await workerFetch(`/internal/ideas/${ideaUuid}/${kind}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contributor_code: me.contributorCode, text: text.slice(0, 2000) }),
  });
  const out = (await res.json().catch(() => ({ error: `${kind}_failed` }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(out.error ?? `${kind}_failed`));
  return out;
}
