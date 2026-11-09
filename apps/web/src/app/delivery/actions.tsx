"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/** Plain words for every refusal the delivery, lenses and learning screens can meet. Never echoed text. */
export const ERRORS: Record<string, string> = {
  forbidden: "You can't do that from your role.",
  own_submission: "Someone other than the person who sent the pack needs to approve it.",
  not_due_yet: "Results can be entered from two working days before they are due.",
  day_30_first: "Confirm the 30-day result first.",
  already_finance_confirmed: "Finance has already confirmed this figure.",
  note_required: "Add the chair's note before sending.",
  already_sent: "This issue has already gone out.",
  not_ready: "The chair needs to approve the note before the issue can go out.",
  own_note: "You wrote or approved this note, so another admin sends the issue.",
  confirm_stale: "The note changed since this page loaded. Reload the page and check it again.",
  chair_only: "Only the core committee chair approves the note.",
  already_ready: "The chair has already approved this note.",
  ember_paused: "Sending The Ember is paused for now.",
  ones_paused: "The Ones are resting from the wall, so The Ember can't go out just now.",
  month_not_valid: "Pick a month.",
  not_found: "We can't find that. It may have moved on, or it isn't one of yours.",
  already_started: "The handover for this has already started.",
  not_picked: "Only picked ideas and groups can start a handover.",
  subject_required: "Pick an idea or group first.",
  subject_not_found: "We can't find that idea or group.",
  track_not_valid: "Pick a track from the list.",
  product_not_valid: "Pick a product from the list.",
  feature_type_not_valid: "Pick a type from the list.",
  compliance_tier_not_valid: "Pick a compliance level from the list.",
  unit_not_valid: "Pick a unit from the list.",
  baseline_not_valid: "The starting number must be a number, zero or more.",
  target_not_valid: "The target must be a number, zero or more.",
  spend_not_valid: "Give the cost centre or budget code (letters, numbers, / and -), or NONE.",
  checklist_not_valid: "The checklist could not be read. Please tick the boxes again.",
  owner_not_found: "We can't find an active colleague with that owner email.",
  sponsor_not_found: "We can't find an active colleague with that sponsor email.",
  pm_not_found: "We can't find an active colleague with that delivery PM email.",
  sponsor_not_a_sponsor: "That person isn't a sponsor yet. An admin can grant the sponsor role.",
  owner_is_sponsor: "The owner and the sponsor must be different people.",
  pack_locked: "The pack can't change once the sponsor has approved it.",
  not_drafting: "This has already gone to the sponsor.",
  pack_incomplete: "The pack isn't complete yet.",
  sponsor_only: "Only the named sponsor can do this.",
  not_awaiting_sponsor: "This isn't waiting for the sponsor.",
  page_id_not_valid: "The page ID should be 8 to 64 letters, numbers or dashes.",
  not_in_delivery: "This isn't being built right now.",
  phase_not_valid: "Pick a step from the list.",
  gate_status_not_valid: "Pick clear or blocked.",
  not_in_fix_track: "This isn't on the fix track right now.",
  due_on_not_valid: "Pick a date within the next year.",
  status_not_valid: "Mark it done or open.",
  before_not_valid: "The number before must be a number, zero or more.",
  after_not_valid: "The number after must be a number, zero or more.",
  nothing_to_approve: "The owner hasn't sent the numbers yet.",
  not_measuring: "This isn't being measured yet.",
  metric_actual_not_valid: "The measured number must be a number, zero or more.",
  capex_inr_not_valid: "One-time cost must be a number in rupees.",
  opex_inr_not_valid: "Running cost must be a number in rupees.",
  adoption_not_valid: "People using it must be a number.",
  time_not_valid: "Give the time as a number and pick a unit.",
  money_not_valid: "Give the money as a number and pick a unit.",
  effort_not_valid: "Give the effort as a number and pick a unit.",
  scale_not_valid: "Give the reach as a number and pick a unit.",
  already_confirmed: "This has already been confirmed.",
  not_filled: "The owner hasn't filled this in yet.",
  own_entry: "Someone else has to confirm this: you filled it in.",
  no_money_figure: "There's no money figure to confirm.",
  verdict_required: "Approve or decline.",
  not_open: "This has already been decided.",
  kind_required: "Pick which report to run.",
  learning_paused: "Learning reports are paused by a switch. Turn it back on first.",
  personal_data: "Please take out any personal details (numbers, addresses, investor names).",
  text_needs_review: "Please reword this: it reads as off-topic or unkind, so we can't save it as it is.",
  names_not_allowed: "Leave out the names of colleagues and clients.",
  text_too_short: "Please write a little more.",
  status_required: "Pick how it's going.",
  owner_only: "Only the owner (or an admin) can do this.",
  not_approved: "Approve the proposal first, then write it into the company repo.",
  already_published: "This one is already being written to the company repo.",
  doc_exists: "The company repo already has a term or tag by that name. Pick another name, or leave it.",
  aliases_not_valid: "Up to eight other spellings, each under 40 characters.",
  name_not_valid: "Use letters or numbers in the name.",
  assistant_unavailable: "The assistant can't draft the pack just now. Please fill it in yourself.",
  nothing_to_draft_from: "There is no idea to draft the pack from.",
  pack_not_open: "The pack can only be drafted before the work starts.",
  writeup_locked: "The write-up is with the sponsor or already published, so it can't be changed now.",
  nothing_to_submit: "Save the write-up first, then submit it.",
  not_submitted: "There is no write-up waiting for a decision.",
  publishing_paused: "Publishing new write-ups is paused for now. Your write-up is saved; approve it later.",
  solution_numbers_full: "We have run out of solution numbers. Please tell the product team.",
  uploader_only: "Only the person who added this file (or an admin) can remove it.",
  closed: "This delivery is closed.",
  not_open_for_evidence: "Files can be added once the work has started, until it closes.",
  too_many_files: "That's the most files this can hold. Remove one first.",
  delivery_total_too_large: "These files together are too large. Remove one first.",
  file_too_large: "That file is too large.",
  file_empty: "That file is empty.",
  file_required: "Choose a file first.",
  type_not_allowed: "That type of file isn't allowed. Use PDF, Word, PowerPoint, Excel, CSV, PNG or JPG.",
  name_has_personal_data: "The file's name looks like it holds personal details. Rename it and try again.",
  text_too_long: "That's too long. Please shorten it.",
  checks_unavailable: "We can't check text just now. Please try again in a few minutes.",
  paused: "This is paused by a switch for now. Please try again once it is back on.",
  try_again: "Someone else changed this at the same moment. Please try again.",
};

/** Plain words for what a pack still needs (the worker's codes). */
export const MISSING_WORDS: Record<string, string> = {
  owner_user_id: "an owner",
  sponsor_user_id: "a sponsor",
  pm_user_id: "the delivery PM",
  metric: "the success metric",
  baseline: "the starting number",
  target: "the target",
  unit: "the unit",
  spend: "the spend reference (or NONE)",
  working_group_formed: "the working group (tick it once formed)",
  baseline_captured: "the baseline (tick it once captured)",
  build_slot_confirmed: "a confirmed build slot",
  dev_slot_confirmed: "a confirmed development slot",
  objective: "the objective",
  // Parts of a solution write-up (BLD-133): a text check names the part it stopped at.
  title: "the title",
  what_it_does: "What it does",
  where_it_runs: "Where it runs",
  result: "The result",
  how_to_adopt: "How another team can adopt it",
};

export const missingText = (codes: string[]) => codes.map((c) => MISSING_WORDS[c] ?? c).join(", ");

async function send(url: string, body: Record<string, unknown>, method: string): Promise<string | null> {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => null);
  if (res?.ok) return null;
  const out = res ? ((await res.json().catch(() => ({}))) as { error?: string; details?: unknown }) : {};
  const code = String(out.error ?? "");
  const words = ERRORS[code] ?? "That didn't work. Please try again.";
  if (code === "pack_incomplete" && Array.isArray(out.details)) {
    return `${words} Still needed: ${missingText(out.details.map(String))}.`;
  }
  if (Array.isArray(out.details) && out.details.length) {
    return `${words} Check: ${missingText(out.details.map(String))}.`; // which part a text check stopped at
  }
  return words;
}

/** Run one action, show its error next to the control, refresh the page and announce success politely. */
export function useAction(onDone: (message: string) => void) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function run(url: string, body: Record<string, unknown>, done: string, method = "POST") {
    if (busy) return false;
    setBusy(true);
    const err = await send(url, body, method);
    setBusy(false);
    setError(err ?? "");
    if (!err) onDone(done);
    return !err;
  }
  return { error, busy, run };
}

export function useDone() {
  const router = useRouter();
  const [status, setStatus] = useState("");
  const done = (message: string) => {
    setStatus(message);
    router.refresh();
  };
  return { status, done };
}

export function Err({ text }: { text: string }) {
  return text ? (
    <p className="field-error" role="alert">
      {text}
    </p>
  ) : null;
}

export function Status({ text }: { text: string }) {
  return (
    <p role="status" aria-live="polite" className="sr-status">
      {text}
    </p>
  );
}
