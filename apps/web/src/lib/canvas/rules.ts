/**
 * Validation and the strength meter (§4.1, AT-B3-02, AT-B3-05). Numbers come from rules/thresholds.md
 * (`canvas`, `canvas_strength`) via the canvas config, so the browser, the server and the review console score
 * a canvas identically. The meter guides; it never blocks submit.
 */
import { scan, type PatternMatch } from "@/lib/pii/patterns";

import { ESTIMATE_FIELDS, textFields, wordCount, type Canvas } from "./model";

export type CanvasLimits = {
  one_line_max_words: number;
  details_min_chars: number;
};

export type StrengthRubric = {
  what_it_is: { one_line_required: boolean; details_min_chars: number };
  who_it_touches: { segments_min: number; plus_any_of: string[] };
  whats_it_worth: { category_not: string; play_required: boolean; figure_any_of: string[] };
  evidence: { basis_any_of: string[]; or_any_reference: boolean; or_clean_attachment: boolean };
  solved_elsewhere: { answer_not: string; our_advantage_required: boolean };
  suggested_counts_only_when_accepted: boolean;
  strong_canvas_min: number;
  nudge_below: number;
};

export type FieldError = { field: string; message: string };

/** The field path of quick capture's single confirmation (its error links to that checkbox). */
export const QUICK_DECLARATION_FIELD = "declarations.all";

/**
 * Required fields (AT-B3-02). Quick capture is one box (DEC-094): the details, visibility and one confirmation
 * covering the three declarations; its category is optional. The full canvas asks for more.
 */
export function validate(c: Canvas, limits: CanvasLimits): FieldError[] {
  const errors: FieldError[] = [];
  const add = (field: string, message: string) => errors.push({ field, message });

  if (c.mode === "full") {
    if (!c.kind) add("kind", "Choose whether this is a problem, a fix or a new business idea.");
    const words = wordCount(c.one_line);
    if (words === 0) add("one_line", "Say it in one line.");
    else if (words > limits.one_line_max_words)
      add("one_line", `Keep the one line to ${limits.one_line_max_words} words or fewer (it has ${words}).`);
    if (c.kind === "problem_with_solution" && !c.solution.approach.trim())
      add("solution.approach", "Tell us how you would solve it, since you have a fix in mind.");
  }
  if (c.details.trim().length < limits.details_min_chars)
    add("details", `Please write at least ${limits.details_min_chars} characters, in any language.`);
  if (c.mode === "full" && !c.value.category)
    add("value.category", "Choose cost saving, new revenue, both, or not sure yet.");
  if (c.visibility === "committee" && c.visibility_reason.trim().length < 10)
    add("visibility_reason", "Tell us briefly why only committees should see this.");
  if (c.mode === "quick") {
    if (!Object.values(c.declarations).every(Boolean))
      add(QUICK_DECLARATION_FIELD, "Please confirm this before you share.");
  } else {
    for (const [key, ok] of Object.entries(c.declarations)) {
      if (!ok) add(`declarations.${key}`, "Please confirm this before you share.");
    }
  }
  return errors;
}

/**
 * What a quick capture saves on submit (DEC-094): a category the person did not choose is saved as "Not sure
 * yet". That is the person's own answer, so the assistant never fills it in for them (DEC-004).
 */
export function finaliseQuick(c: Canvas): Canvas {
  if (c.mode !== "quick" || c.value.category) return c;
  return { ...c, value: { ...c.value, category: "not_sure" } };
}

export type PersonalDataHit = { field: string; match: PatternMatch };

/** The level-1 personal-data check over every text field (§4.2 step 2). */
export function personalData(c: Canvas, kfinDomains: string[]): PersonalDataHit[] {
  return textFields(c).flatMap(([field, text]) => scan(text, kfinDomains).map((match) => ({ field, match })));
}

export const blocks = (hits: PersonalDataHit[]) => hits.some((h) => h.match.action === "block");

export type Strength = { score: number; points: Record<string, boolean>; nextBest: string[] };

/** 0–5 (BLD-021): one point per rubric line; the two most useful additions next. */
export function strength(c: Canvas, rubric: StrengthRubric, cleanAttachments = 0): Strength {
  // A suggested answer counts only once the person accepts it.
  const has = (path: string, value: unknown) => {
    if (rubric.suggested_counts_only_when_accepted && c.provenance[path] === "suggested") return false;
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === "number") return Number.isFinite(value);
    return typeof value === "string" ? value.trim().length > 0 : value !== null && value !== undefined;
  };
  const r = rubric;
  const prompts: string[] = [];

  const lineOk = !r.what_it_is.one_line_required || has("one_line", c.one_line);
  const detailsOk = c.details.trim().length >= r.what_it_is.details_min_chars;
  const whatItIs = lineOk && detailsOk;
  if (!lineOk) prompts.push("Say it in one line");
  else if (!detailsOk) prompts.push("Tell us a little more: a few sentences on what happens and where");

  const segmentsOk =
    c.who.segments.length >= r.who_it_touches.segments_min && has("who.segments", c.who.segments);
  const sizeOk = r.who_it_touches.plus_any_of.some((f) =>
    has(`who.${f}`, (c.who as Record<string, unknown>)[f] ?? ""),
  );
  const whoItTouches = segmentsOk && sizeOk;

  const categoryOk = Boolean(c.value.category) && c.value.category !== r.whats_it_worth.category_not;
  const playOk = !r.whats_it_worth.play_required || has("value.play", c.value.play);
  const figureOk = r.whats_it_worth.figure_any_of.some((f) =>
    has(`value.estimate.${f}`, (c.value.estimate as Record<string, unknown>)[f]),
  );
  const worth = categoryOk && playOk && figureOk;
  if (!categoryOk) prompts.push("Say whether it saves cost, earns revenue, or both");
  else if (!playOk) prompts.push("Say how KFintech benefits");
  else if (!figureOk) prompts.push("Add a rough ₹ or hours estimate");

  if (!segmentsOk) prompts.push("Say who feels this or would pay for it");
  else if (!sizeOk) prompts.push("Say how often it happens, or what people do today instead");

  const evidence =
    (Boolean(c.value.basis) && r.evidence.basis_any_of.includes(c.value.basis ?? "")) ||
    (r.evidence.or_any_reference && c.ecosystem.references.some((ref) => ref.value.trim())) ||
    (r.evidence.or_clean_attachment && cleanAttachments > 0);
  if (!evidence) prompts.push("Say what your estimate is based on, or add a link or a file");

  const answered =
    Boolean(c.ecosystem.solved_elsewhere) && c.ecosystem.solved_elsewhere !== r.solved_elsewhere.answer_not;
  const advantageOk =
    !r.solved_elsewhere.our_advantage_required || has("ecosystem.our_advantage", c.ecosystem.our_advantage);
  const solved = answered && advantageOk;
  if (!answered) prompts.push("Tell us if a competitor or another team already does this");
  else if (!advantageOk) prompts.push("Say why KFintech should do this, or do it better");

  const points = {
    what_it_is: whatItIs,
    who_it_touches: whoItTouches,
    whats_it_worth: worth,
    evidence,
    solved_elsewhere: solved,
  };
  return { score: Object.values(points).filter(Boolean).length, points, nextBest: prompts.slice(0, 2) };
}

/** Number inputs: blank is null; negatives and junk are refused rather than guessed. */
export function parseFigure(raw: string): number | null | "invalid" {
  const cleaned = raw.replace(/[,\s₹]/g, "");
  if (!cleaned) return null;
  const n = Number(cleaned);
  return Number.isFinite(n) && n >= 0 ? n : "invalid";
}

export const ESTIMATE_KEYS = ESTIMATE_FIELDS.map(([k]) => k);
