/**
 * Delivery (§4.8 to §4.11), lenses (§4.14) and learning (§5), web side. Every read and write goes through the
 * worker, which checks the person's part in each delivery again; this module passes who is acting and turns
 * refusals into codes (never echoed text). A pack that is not complete comes back with the missing items.
 */
import type { CurrentUser } from "./auth/current";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

export type Person = { name: string; email: string };
export type Track = "build" | "fix" | "procurement";
export type DeliveryState =
  "drafting" | "awaiting_sponsor" | "in_delivery" | "shipped" | "resolved" | "closed";
export type Mark = "day_30" | "day_90";
export type MeasureInput = { value: number; unit: string };

export type DeliveryRow = {
  id: number;
  subject_id: string;
  subject_type: "idea" | "cluster";
  label: string;
  track: Track;
  track_words: string;
  state: DeliveryState;
  state_words: string;
  phase_words: string | null;
  blocked: boolean;
  owner: string | null;
  sponsor: string | null;
  next_measurement: { mark: Mark; due_at: string; filled: boolean } | null;
  outcome: "target_met" | "target_not_met" | null;
  updated_at: string;
};

export type DeliveryConsole = {
  deliveries: DeliveryRow[];
  waiting: { subject_type: "idea" | "cluster"; subject_id: string; label: string }[];
  can_start: boolean;
};

export type Measurement = {
  mark: Mark;
  due_at: string;
  results: {
    metric_actual?: number;
    capex_inr?: number;
    opex_inr?: number;
    adoption?: number;
    target_met?: boolean | null;
    actual_vs_target?: number | null;
  } & Partial<Record<"time" | "money" | "effort" | "scale", MeasureInput>>;
  notes: string | null;
  filled_at: string | null;
  confirmed_at: string | null;
  finance_confirmed: boolean;
  can_fill: boolean;
  can_confirm: boolean;
  can_finance_confirm: boolean;
};

export type Milestone = {
  id: number;
  title: string | null;
  owner: string | null;
  due_on: string;
  status: "open" | "done";
  overdue: boolean;
  can_set: boolean;
};

export type EvidenceFile = {
  id: string;
  name: string;
  bytes: number;
  state: "quarantine" | "processing" | "awaiting_check" | "clean" | "rejected";
  state_words: string;
  rejection_words: string | null;
  can_open: boolean;
  can_remove: boolean;
  added_at: string | null;
};

export type CheckinStatus = "on_track" | "at_risk" | "blocked";
export type Checkins = {
  recent: { week_of: string; status: CheckinStatus; status_words: string; note: string | null }[];
  this_week: string;
  replied_this_week: boolean;
  can_reply: boolean;
  statuses: { id: CheckinStatus; words: string }[];
};

/** The write-up other teams can adopt (BLD-133). `parts` only for the people on the delivery. */
export type WriteupPart = "title" | "what_it_does" | "where_it_runs" | "result" | "how_to_adopt";
export type Writeup = {
  state: "draft" | "submitted" | "approved" | "sent_back" | null;
  state_words: string;
  parts: Record<WriteupPart, string> | null;
  solution_id: string | null;
  can_edit: boolean;
  can_submit: boolean;
  can_decide: boolean;
};

export type DeliveryDetail = {
  id: number;
  subject_id: string;
  subject_type: "idea" | "cluster";
  label: string;
  track: Track;
  track_words: string;
  state: DeliveryState;
  state_words: string;
  owner: Person | null;
  sponsor: Person | null;
  pm: Person | null;
  pack: {
    product?: string;
    feature_type?: string;
    compliance_tier?: string;
    unit?: string | null;
    baseline?: number | null;
    target?: number | null;
    spend?: string | null;
    checklist?: Record<string, boolean>;
  };
  metric: string | null;
  objective: string | null;
  missing: string[];
  sponsor_approved_at: string | null;
  phase: string | null;
  phase_words: string | null;
  gate_status: "clear" | "blocked" | null;
  blocked_since: string | null;
  link_state: "none" | "queued" | "manual" | "linked";
  pipeline_page_id: string | null;
  completion: { before: number; after: number; unit: string | null } | null;
  completion_notes: string | null;
  completed_at: string | null;
  milestones: Milestone[];
  measurements: Measurement[];
  evidence: EvidenceFile[];
  checkins: Checkins | null;
  writeup: Writeup | null;
  outcome: "target_met" | "target_not_met" | null;
  shipped_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  options: {
    tracks: Track[];
    products: string[];
    feature_types: string[];
    compliance_tiers: string[];
    metric_units: string[];
    phases: { id: string; words: string }[];
    measure_units: Record<"time" | "money" | "effort" | "scale", string[]>;
  };
  can: Record<
    | "edit"
    | "submit"
    | "approve"
    | "set_phase"
    | "link"
    | "add_milestone"
    | "complete"
    | "approve_completion"
    | "add_evidence",
    boolean
  >;
};

export type LensStages = Record<string, number>;
export type Lenses = {
  built_at: string | null;
  stage_groups: string[];
  lobs: {
    id: string;
    name: string;
    ideas: number;
    stages: LensStages;
    ageing: number;
    top_groups: { id: string; ideas: number; colleagues: number }[];
    cross_lob_groups: number;
    being_built: number;
    measuring: number;
    closed: number;
    adoptable: number;
  }[];
  roles: {
    id: string;
    name: string;
    ideas: number;
    stages: LensStages;
    top_areas: { id: string; name: string; ideas: number }[];
  }[];
  people: { id: string; colleagues: number; related_groups: number; could_join: number }[];
  can_rebuild: boolean;
};

export type LearningProposal = {
  id: number;
  kind: "area_tag" | "glossary_term";
  period: string;
  state: "proposed" | "approved" | "declined";
  term: string | null;
  ideas: number | null;
  idea_ids: string[];
  current_tags: Record<string, number> | null;
  lobs: Record<string, number> | null;
  decided_at: string | null;
  /** BLD-136: the company repo file it was written to (GL-… or AREA-…), and whether the repo writer has run. */
  doc_id: string | null;
  in_repo: boolean;
  can_publish: boolean;
};

export type Learning = {
  switched_on: boolean;
  reports: Partial<
    Record<
      "autonomy" | "drift" | "canvas" | "calibration",
      { period: string; data: Record<string, unknown>; built_at: string }
    >
  >;
  autonomy: { action_type: string; mode: "gated" | "auto"; rate: number | null; window: number }[];
  proposals: LearningProposal[];
};

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await workerFetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    signal: AbortSignal.timeout(30_000),
  });
  const out = (await res.json().catch(() => ({ error: "delivery_unavailable" }))) as Record<string, unknown>;
  if (!res.ok) {
    const missing = Array.isArray(out.missing) ? out.missing.map(String) : undefined;
    throw new SubmissionError(res.status, String(out.error ?? "delivery_unavailable"), missing);
  }
  return out as T;
}

const send = <T>(me: CurrentUser, path: string, input: unknown = {}, method = "POST") =>
  call<T>(path, { method, body: JSON.stringify({ ...body(input), actor_user_id: me.id }) });

/** Numeric IDs only; anything else is "not found" before it reaches the worker. */
export const id = (value: string) => {
  if (!/^[0-9]{1,12}$/.test(value)) throw new SubmissionError(404, "not_found");
  return value;
};

const mark = (value: string): Mark => {
  if (value !== "day_30" && value !== "day_90") throw new SubmissionError(404, "not_found");
  return value;
};

const body = (input: unknown): Record<string, unknown> =>
  input && typeof input === "object" && !Array.isArray(input) ? (input as Record<string, unknown>) : {};

const base = (deliveryId: string) => `/internal/delivery/${id(deliveryId)}`;

// --- Delivery -----------------------------------------------------------------------------------------------------

export const deliveryConsole = (me: CurrentUser) =>
  call<DeliveryConsole>(`/internal/delivery/console/${me.id}`);

export async function deliveryDetail(me: CurrentUser, deliveryId: string): Promise<DeliveryDetail | null> {
  if (!/^[0-9]{1,12}$/.test(deliveryId)) return null;
  const res = await workerFetch(`/internal/delivery/${deliveryId}/view/${me.id}`, {
    signal: AbortSignal.timeout(30_000),
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new SubmissionError(502, "delivery_unavailable");
  return (await res.json()) as DeliveryDetail;
}

export const startHandover = (me: CurrentUser, input: unknown) =>
  send<{ id: number }>(me, "/internal/delivery", input);

export const savePack = (me: CurrentUser, deliveryId: string, input: unknown) =>
  send(me, `${base(deliveryId)}/pack`, input, "PUT");

export const submitPack = (me: CurrentUser, deliveryId: string) => send(me, `${base(deliveryId)}/submit`);
export const approvePack = (me: CurrentUser, deliveryId: string) => send(me, `${base(deliveryId)}/approve`);
export const sendBack = (me: CurrentUser, deliveryId: string) => send(me, `${base(deliveryId)}/send-back`);
export const linkPage = (me: CurrentUser, deliveryId: string, input: unknown) =>
  send(me, `${base(deliveryId)}/link`, input);
export const setPhase = (me: CurrentUser, deliveryId: string, input: unknown) =>
  send(me, `${base(deliveryId)}/phase`, input);
export const addMilestone = (me: CurrentUser, deliveryId: string, input: unknown) =>
  send<{ id: number }>(me, `${base(deliveryId)}/milestones`, input);
export const setMilestone = (me: CurrentUser, deliveryId: string, milestoneId: string, input: unknown) =>
  send(me, `${base(deliveryId)}/milestones/${id(milestoneId)}`, input);
export const completeFix = (me: CurrentUser, deliveryId: string, input: unknown) =>
  send(me, `${base(deliveryId)}/complete`, input);
export const approveCompletion = (me: CurrentUser, deliveryId: string) =>
  send(me, `${base(deliveryId)}/approve-completion`);
export const fillMeasurement = (me: CurrentUser, deliveryId: string, m: string, input: unknown) =>
  send(me, `${base(deliveryId)}/measurements/${mark(m)}`, input, "PUT");
export const confirmMeasurement = (me: CurrentUser, deliveryId: string, m: string) =>
  send(me, `${base(deliveryId)}/measurements/${mark(m)}/confirm`);
export const financeConfirm = (me: CurrentUser, deliveryId: string, m: string) =>
  send(me, `${base(deliveryId)}/measurements/${mark(m)}/finance`);

// --- Lenses and learning --------------------------------------------------------------------------------------------

export const lenses = (me: CurrentUser) => call<Lenses>(`/internal/lenses/${me.id}`);
export const rebuildLenses = (me: CurrentUser) =>
  send<{ lobs: number; roles: number }>(me, "/internal/lenses/rebuild");
export const learning = (me: CurrentUser) => call<Learning>(`/internal/learning/${me.id}`);
export const decideLearning = (me: CurrentUser, proposalId: string, input: unknown) =>
  send(me, `/internal/learning/proposals/${id(proposalId)}/decide`, input);
export const publishProposal = (me: CurrentUser, proposalId: string, input: unknown) =>
  send(me, `/internal/learning/proposals/${id(proposalId)}/publish`, input);
export const runLearning = (me: CurrentUser, input: unknown) => send(me, "/internal/learning/run", input);

// --- Evidence files and Friday check-ins (BLD-131, BLD-132) -------------------------------------------------------

const ATT = /^ATT-[0-9]{4}-[0-9]{6}$/;

export async function uploadEvidence(me: CurrentUser, deliveryId: string, file: File) {
  const form = new FormData();
  form.set("actor_user_id", me.id);
  form.set("file", file, file.name.slice(0, 200));
  const res = await workerFetch(`${base(deliveryId)}/evidence`, {
    method: "POST",
    body: form,
    signal: AbortSignal.timeout(60_000),
  });
  const out = (await res.json().catch(() => ({ error: "upload_failed" }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(out.error ?? "upload_failed"));
  return out;
}

/** The worker checks that the person can see the delivery and that the file is clean. */
export async function evidenceContent(me: CurrentUser, deliveryId: string, attId: string) {
  if (!ATT.test(attId)) throw new SubmissionError(404, "not_found");
  return workerFetch(`${base(deliveryId)}/evidence/${attId}/content/${me.id}`, {
    signal: AbortSignal.timeout(300_000),
  });
}

export const removeEvidence = (me: CurrentUser, deliveryId: string, attId: string) => {
  if (!ATT.test(attId)) throw new SubmissionError(404, "not_found");
  return send(me, `${base(deliveryId)}/evidence/${attId}/remove`);
};

export const checkIn = (me: CurrentUser, deliveryId: string, input: unknown) =>
  send(me, `${base(deliveryId)}/checkin`, input);

export const saveWriteup = (me: CurrentUser, deliveryId: string, input: unknown) =>
  send(me, `${base(deliveryId)}/writeup`, input, "PUT");

const WRITEUP_STEPS = ["submit", "approve", "send-back"] as const;
export type WriteupStep = (typeof WRITEUP_STEPS)[number];
export const writeupStep = (me: CurrentUser, deliveryId: string, step: string) => {
  if (!(WRITEUP_STEPS as readonly string[]).includes(step)) throw new SubmissionError(404, "not_found");
  return send(me, `${base(deliveryId)}/writeup/${step}`);
};
