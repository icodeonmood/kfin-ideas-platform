/**
 * P-PRODUCT.promises (BLD-A181): the times, windows and minimum lengths the app shows people and keeps to. They
 * live in the company repo's rules/promises.md, read by the worker, so a change needs no release. Read on the
 * server; cached for a minute per process.
 */
import { workerFetch } from "./worker";

export type Promises = {
  version: string;
  draft: { min_chars_to_check: number; kept_days: number };
  voice: { max_seconds: number };
  review: { decide_by_working_days: number };
  edit_window: { max_days: number };
  questions: {
    answer_options_days: number[];
    answer_default_days: number;
    deadline_hour: number;
    reminder_hours_before: number[];
    extend_by_days: number;
  };
  notes: {
    decision_reason_min_chars: number;
    reversal_note_min_chars: number;
    teamup_note_min_chars: number;
    merge_note_min_chars: number;
  };
  committee_window: { days: number; extend_by_days: number; max_months: number };
  not_now: { return_options_months: number[]; return_default_months: number };
  team_by: { working_days: number };
  impact: { check_days: number[] };
  sign_in: {
    code_digits: number;
    code_valid_minutes: number;
    code_tries: number;
    resend_after_seconds: number;
  };
  session: { hours: number };
  ones: { number_change_days: number; number_max: number };
};

const TTL_MS = 60_000;
let cached: { at: number; value: Promises } | undefined;

export async function promises(): Promise<Promises> {
  if (cached && Date.now() - cached.at < TTL_MS) return cached.value;
  const res = await workerFetch("/internal/config/promises");
  if (!res.ok) throw new Error("promises_unavailable");
  const value = (await res.json()) as Promises;
  cached = { at: Date.now(), value };
  return value;
}
