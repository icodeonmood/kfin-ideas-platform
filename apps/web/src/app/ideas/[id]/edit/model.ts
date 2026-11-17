/**
 * S-06B's rules that need no screen (L-SUBMIT.edit, L-SORT): what the person has changed since the page loaded,
 * the Save body with only those changes, the sorting as it reads with them, and where a refusal's words go. Pure
 * functions, so the vitest suite covers them without a browser.
 */
import type { Brings, EditPageResponse, FixRequest, IdeaPatch, Kind, SortingResponse } from "@/lib/contracts";

import type { FixPart } from "@/app/share/[id]/check/fix";
import { fixRequest, type FixForm, type ProofItem } from "@/app/share/[id]/check/model";

/** The sorting fields as the person changes them, held until Save. */
export interface SortingPending {
  affects?: string[];
  kind?: Kind;
  area?: string;
  brings?: Brings[];
}

/** Everything on the page that waits for Save (L-SUBMIT.edit/2). Files, links and "Show it" act at once; the
 * files and links added or removed are counted from the rows (`filesDelta`), so Cancel and Save know them too. */
export interface EditState {
  title: string;
  summary: string;
  often: string;
  sorting: SortingPending;
  fix: { part: FixPart; form: FixForm; touched: boolean };
}

export function initialState(page: EditPageResponse, emptyFix: FixForm, form: FixForm): EditState {
  return {
    title: page.fields.title,
    summary: page.fields.summary,
    often: page.fields.often ?? "",
    sorting: {},
    fix: { part: fixPartOf(page), form: page.fix ? form : emptyFix, touched: false },
  };
}

/** The fix part as the server words it (S-05.parts/5), or "Add your fix". */
export function fixPartOf(page: EditPageResponse): FixPart {
  const p = page.fix?.part;
  if (p && p.rail === "Added") {
    return { kind: "added", line: p.line, fixLine: p.fix_line, sizeLine: p.size_line };
  }
  return { kind: "none" };
}

const sameSet = (a: readonly string[] | null | undefined, b: readonly string[] | null | undefined) => {
  const x = new Set(a ?? []);
  const y = new Set(b ?? []);
  return x.size === y.size && [...x].every((v) => y.has(v));
};

const FIELDS = ["affects", "kind", "area", "brings"] as const;
type Field = (typeof FIELDS)[number];

function differs(s: SortingResponse, f: Field, v: unknown): boolean {
  if (f === "affects" || f === "brings") return !sameSet(s[f].value as string[], v as string[]);
  return s[f].value !== v;
}

/** Only the sorting fields whose value is not what was loaded. */
export function sortingChanges(s: SortingResponse, pending: SortingPending): SortingPending {
  const out: SortingPending = {};
  for (const f of FIELDS) {
    if (!(f in pending)) continue;
    const v = pending[f];
    if (differs(s, f, v)) (out as Record<Field, unknown>)[f] = v;
  }
  return out;
}

/**
 * The sorting as it reads with the person's changes: a changed field loses its "Suggested because …" (it is their
 * call now), and the card stays confirmed unless a required field is empty (S-06B.rules/3, V-FIELDS.checkit/3).
 */
export function sortingView(s: SortingResponse, pending: SortingPending): SortingResponse {
  const next: SortingResponse = { ...s };
  for (const f of FIELDS) {
    if (!(f in pending)) continue;
    const v = pending[f];
    const changed = differs(s, f, v);
    (next as unknown as Record<Field, unknown>)[f] = {
      ...s[f],
      value: v,
      why_line: changed ? null : s[f].why_line,
    };
  }
  const complete =
    (next.affects.value ?? []).length > 0 &&
    Boolean(next.kind.value) &&
    Boolean(next.area.value) &&
    (next.brings.value ?? []).length > 0;
  return { ...next, complete, confirmed: complete };
}

/** How would you solve it: at least 20 characters to add a fix (V-FIELDS.checkit/8, `submit/fix.py` HOW_MIN). */
export const HOW_MIN = 20;

/** The fix to send: the added one, `null` for "Remove", or nothing when it is as loaded. A started fix that was
 * never added stays on this page only: the edit page saves a fix only when it is added (BLD-C162). */
export function fixPatch(hadFix: boolean, fix: EditState["fix"]): FixRequest | null | undefined {
  if (!fix.touched) return undefined;
  if (fix.part.kind === "added") {
    const answers = fixRequest(fix.form, true);
    delete answers.included; // the edit page's fix is always the added one (`submit/edit.py` _save_fix)
    return answers;
  }
  return hadFix ? null : undefined;
}

/**
 * The files and links added or removed on this page since it was loaded or last saved (BLD-C161, as amended in
 * review): `base` is the IDs the page started from. They went in, or out, at once; they count as unsaved changes
 * (Cancel confirms and takes the added ones away again), and Save records them in the version.
 */
export interface FilesDelta {
  added: string[];
  removed: string[];
  /** A file still on its way up: it lands on the idea, so leaving now is leaving a change. */
  moving: boolean;
}

export const NO_FILES: FilesDelta = { added: [], removed: [], moving: false };

const fileId = (r: ProofItem) => r.item?.id ?? null;

export function filesDelta(base: readonly string[], rows: readonly ProofItem[]): FilesDelta {
  const had = new Set(base);
  const now = rows.map(fileId).filter((id): id is string => Boolean(id));
  const has = new Set(now);
  return {
    added: now.filter((id) => !had.has(id)),
    removed: base.filter((id) => !has.has(id)),
    moving: rows.some((r) => !fileId(r) && r.localState === "uploading"),
  };
}

/** The rows this page added (on the server or still only here): what Cancel takes away again. */
export function addedRows(base: readonly string[], rows: readonly ProofItem[]): ProofItem[] {
  const had = new Set(base);
  return rows.filter((r) => {
    const id = fileId(r);
    return id ? !had.has(id) : true;
  });
}

/** After a save: the IDs the page now starts from, from what that save sent. */
export function baseAfter(base: readonly string[], sent: FilesDelta): string[] {
  const out = base.filter((id) => !sent.removed.includes(id));
  for (const id of sent.added) if (!out.includes(id)) out.push(id);
  return out;
}

/** Save's body: only what changed (A-API `PATCH /ideas/:id`). The server compares again and words the outcome. */
export function editPatch(page: EditPageResponse, state: EditState, files: FilesDelta = NO_FILES): IdeaPatch {
  const out: IdeaPatch = {};
  if (state.title.trim() !== page.fields.title.trim()) out.title = state.title.trim();
  if (state.summary.trim() !== page.fields.summary.trim()) out.summary = state.summary.trim();
  const often = state.often.trim();
  if (often !== (page.fields.often ?? "").trim()) out.often = often || null;
  const sorting = sortingChanges(page.sorting, state.sorting);
  if (Object.keys(sorting).length) out.sorting = sorting;
  const fix = fixPatch(page.fix !== null, state.fix);
  if (fix !== undefined) out.fix = fix;
  if (files.added.length || files.removed.length) out.files = { added: files.added, removed: files.removed };
  return out;
}

/** "Unsaved changes" (C-TASKBAR.save): anything Save would send, or a file still on its way up. */
export function isDirty(page: EditPageResponse, state: EditState, files: FilesDelta = NO_FILES): boolean {
  return Object.keys(editPatch(page, state, files)).length > 0 || files.moving;
}

/**
 * After a save, the page as the server now has it, keeping anything changed while the save was on its way: a field
 * that differs from what was sent stays as the person left it; the rest take the server's values (the masked copy).
 */
export function rebase(sent: EditState, current: EditState, fresh: EditState): EditState {
  const keep = <K extends keyof EditState>(k: K): EditState[K] =>
    Object.is(current[k], sent[k]) ? fresh[k] : current[k];
  return {
    title: keep("title"),
    summary: keep("summary"),
    often: keep("often"),
    sorting: keep("sorting"),
    fix: keep("fix"),
  };
}

/** The drawn labels the carried-over words go under (Edit.md, PhoneEdit.md, the fix sheet). */
export interface PrefillLabels {
  title: string;
  summary: string;
  often: string;
  how: string;
}

/**
 * S-06B.rules/2: the person's own changed words, as plain text for the conversation's message box ("Your changes
 * are kept below. Send them as a message instead."). Only words: the sorting and files are not carried. Empty when
 * no words changed.
 */
export function prefillText(page: EditPageResponse, state: EditState, labels: PrefillLabels): string {
  const patch = editPatch(page, state);
  const lines: string[] = [];
  if (patch.title) lines.push(`${labels.title}: ${patch.title}`);
  if (patch.summary) lines.push(`${labels.summary}: ${patch.summary}`);
  if (typeof patch.often === "string" && patch.often) lines.push(`${labels.often}: ${patch.often}`);
  if (patch.fix?.how?.trim()) lines.push(`${labels.how} ${patch.fix.how.trim()}`);
  return lines.join("\n\n");
}

/** Where a refusal's words go: under the part it is about, else under Save. */
export type ErrorPlace = "words" | "sorting" | "fix" | "save";

export function placeOf(field: string | undefined): ErrorPlace {
  if (!field) return "save";
  if (field === "title" || field === "summary" || field === "often") return "words";
  if (field === "sorting" || field.startsWith("sorting.")) return "sorting";
  if (field === "fix" || field.startsWith("fix.")) return "fix";
  return "save";
}

/** After a save whose page could not be read again: what was sent becomes what the page compares against. */
export function afterSave(
  page: EditPageResponse,
  state: EditState,
): { page: EditPageResponse; state: EditState } {
  const often = state.often.trim();
  return {
    page: {
      ...page,
      fields: { title: state.title.trim(), summary: state.summary.trim(), often: often || null },
      sorting: sortingView(page.sorting, state.sorting),
    },
    state: { ...state, sorting: {}, fix: { ...state.fix, touched: false } },
  };
}
