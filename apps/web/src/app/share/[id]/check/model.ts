/**
 * S-05's rules that need no screen: which part comes next, what each rail row says, how a file's state reads
 * (C-FILE.row), what a similar idea's tile shows after a request (C-SIMGRID.tile), and how ready a fix is
 * (S-05.fix). Pure functions, so the vitest suite covers them without a browser.
 */
import type { FileStatus } from "@/components/ui/file";
import type { DraftStep, FileItem, FixRequest, SimilarMatch, SortingResponse } from "@/lib/contracts";

import { CHECK_COPY, type PartNo } from "./copy";
import type { MergeState } from "./client";

const C = CHECK_COPY;

/** "check:3" → 3; "send" → 7; anything else → 1 (L-DRAFT: Check it opens where the person left it). */
export function partFromStep(step: DraftStep | string | undefined | null): PartNo {
  if (step === "send" || step === "check:7") return 7;
  const m = /^check:([1-7])$/.exec(step ?? "");
  return m ? (Number(m[1]) as PartNo) : 1;
}

export function stepOf(part: PartNo): DraftStep {
  return part === 7 ? "send" : (`check:${part}` as DraftStep);
}

/** The phone's "3 sortings" (PhoneReview.md): the sorting fields that hold a value, of the four (BLD-C138). */
export function sortingCount(s: SortingResponse | null): number {
  if (!s) return 0;
  return [s.affects.value?.length, s.kind.value, s.area.value, s.brings.value?.length].filter(Boolean).length;
}

// ---------------------------------------------------------------------------------------------------------------
// The order of the parts: flag S2 "Check first" (P-DECISIONS.experiments, L-SIMILAR "Flag S2"; BLD-C176)
// ---------------------------------------------------------------------------------------------------------------

/** The parts as drawn: your words, sorting, similar ideas, proof, your fix, who would help, send it. */
export const DEFAULT_ORDER: readonly PartNo[] = [1, 2, 3, 4, 5, 6, 7];
/** "Check first" on a close match: similar ideas first, then your words and sorting, then the rest (Review.md,
 * `simulatorS2=Check first`). */
export const CHECK_FIRST_ORDER: readonly PartNo[] = [3, 1, 2, 4, 5, 6, 7];

/** The match that puts the comparison first: the top match, when L-SIMILAR calls it `close`. None otherwise. */
export function strongMatch(load: SimilarLoad): SimilarMatch | null {
  const top = load.state === "ok" ? load.matches[0] : undefined;
  return top && top.strength === "close" ? top : null;
}

/** The part after `n` in this order, or `n` itself at the end. */
export function nextIn(order: readonly PartNo[], n: PartNo): PartNo {
  const i = order.indexOf(n);
  return i >= 0 && i < order.length - 1 ? order[i + 1]! : n;
}

/** The part before `n` in this order, or null when `n` comes first. */
export function prevIn(order: readonly PartNo[], n: PartNo): PartNo | null {
  const i = order.indexOf(n);
  return i > 0 ? order[i - 1]! : null;
}

/** Where `n` stands in this order, counting from 1: the rail's number and "Check it, part 1 of 6". */
export function placeIn(order: readonly PartNo[], n: PartNo): number {
  const i = order.indexOf(n);
  return i >= 0 ? i + 1 : n;
}

// ---------------------------------------------------------------------------------------------------------------
// Similar ideas and the merge request
// ---------------------------------------------------------------------------------------------------------------

export type SimilarLoad =
  { state: "loading" } | { state: "failed" } | { state: "ok"; matches: SimilarMatch[] };

function firstName(p: { first_name?: string; name: string } | undefined): string {
  if (!p) return "";
  return p.first_name || p.name.split(/\s+/)[0] || p.name;
}

/** What the merge request means for Check it: lane F's words when sent, else the pack's drawn lines. */
export interface MergeView {
  state: "waiting" | "accepted" | "team_only" | "declined";
  otherId: string;
  rail: string;
  line: string;
  action: { label: string; op?: string; to?: string } | null;
  canSubmit: boolean;
}

export function mergeView(merge: MergeState | null, matches: SimilarMatch[]): MergeView | null {
  if (!merge || !merge.after) {
    if (!merge || !merge.other_idea_id) return null;
    if (merge.state !== "waiting" && merge.state !== "accepted") return null;
    // NOT DRAWN by the route: compose the drawn lines from the lead's first name.
    const lead = merge.lead ?? matches.find((m) => m.idea.id === merge.other_idea_id)?.idea.lead;
    const first = firstName(lead);
    if (merge.state === "accepted") return mergedView(merge.other_idea_id, null, first);
    if (!first) return null;
    return {
      state: "waiting",
      otherId: merge.other_idea_id,
      rail: C.similar.merge.waitingRail(first),
      line: C.similar.merge.waitingLine(first),
      action: { label: C.similar.merge.withdraw, op: "withdraw" },
      canSubmit: false,
    };
  }
  const a = merge.after;
  const state = a.state as MergeView["state"];
  if (!["waiting", "accepted", "team_only", "declined"].includes(state)) return null;
  return {
    state,
    otherId: merge.other_idea_id ?? "",
    rail: a.label ?? "",
    line: a.line,
    action: a.action ?? null,
    canSubmit: a.can_submit ?? (state !== "waiting" && state !== "accepted"),
  };
}

/**
 * L-MERGE.request/5 (J-SIMILAR/6a, BLD-C155): a draft closed as merged into `ref`. Lane F's words when its read
 * answered "accepted"; else the drawn ones: "Merged into IDEA-…", "{first} accepted. Yours is now part of IDEA-…,
 * with credit to you. Nothing else to send." (only with the lead's first name; the bar then says just the link) and
 * "See the merged idea". Null for a draft that is not merged.
 */
export function mergedView(
  ref: string | null | undefined,
  merge: MergeView | null,
  first = "",
): MergeView | null {
  if (merge?.state === "accepted") return merge;
  if (!ref) return null;
  return {
    state: "accepted",
    otherId: ref,
    rail: C.similar.merge.acceptedRail(ref),
    line: first ? C.similar.merge.acceptedLine(first, ref) : "",
    action: { label: C.similar.merge.seeMerged, to: `/ideas/${encodeURIComponent(ref)}` },
    canSubmit: false,
  };
}

/**
 * BLD-C156: the parts a reload shows ticked from what the server keeps, not from clicks in memory. Moving on from a
 * part saves the next one as the draft's `step` (S-05 saves where the person is), so a saved step past a part means
 * the person moved on from it: "Looks right" for part 1, "Next" for part 3, and so on. Sorting (part 2) is ticked
 * only when confirmed and Send it (part 7) never, so neither is here. Part 3 is also done once "Keep mine separate"
 * is kept or a merge request has an answer, and part 5 once a fix is added; check-it.tsx adds those.
 */
export function passedParts(step: DraftStep | string | undefined | null): ReadonlySet<PartNo> {
  if (step !== "send" && !/^check:[1-7]$/.test(step ?? "")) return new Set();
  const at = partFromStep(step);
  const out = new Set<PartNo>();
  for (let n = 1; n < at; n++) if (n !== 2) out.add(n as PartNo);
  return out;
}

/** A tile's action row (C-SIMGRID.tile): "Team up", "Waiting for Ravi" + "Withdraw", or "On the crew". */
export type TileAction =
  | { kind: "team-up" }
  | { kind: "waiting"; label: string; withdraw: { merge: true } | { requestId: string } }
  | { kind: "on-crew" }
  /** L-TEAMUP refuses a team-up here (BLD-C187): the tile keeps Preview and offers nothing else. */
  | { kind: "none" };

/** A tile's action (C-SIMGRID.tile): waiting and on the crew as before; then, where lane F's L-TEAMUP.rules/1 check
 * (`can_team_up`) refuses, "On the crew" when the viewer is on it, else nothing; else "Team up" (BLD-C187). */
export function tileAction(match: SimilarMatch, merge: MergeView | null): TileAction {
  const first = firstName(match.idea.lead);
  if (merge && merge.otherId === match.idea.id && merge.state === "waiting") {
    return { kind: "waiting", label: C.similar.waiting(first), withdraw: { merge: true } };
  }
  const r = match.my_request;
  if (r) {
    if (r.state === "sent") {
      return { kind: "waiting", label: C.similar.waiting(first), withdraw: { requestId: r.id } };
    }
    if (r.state === "approved_merged" || r.state === "approved_team_only") return { kind: "on-crew" };
  }
  if (
    merge &&
    merge.otherId === match.idea.id &&
    (merge.state === "accepted" || merge.state === "team_only")
  ) {
    return { kind: "on-crew" };
  }
  if (match.can_team_up === false) {
    return match.team_up_why_not === "already_on_crew" ? { kind: "on-crew" } : { kind: "none" };
  }
  return { kind: "team-up" };
}

/** The rail's line for part 3 (S-05.layout): a merge outcome, else the count, else none or couldn't check. */
export function similarRail(load: SimilarLoad, merge: MergeView | null): string {
  if (merge && merge.rail) return merge.rail;
  if (load.state === "failed") return C.similar.couldnt;
  if (load.state !== "ok") return "";
  if (!load.matches.length) return C.similar.none;
  return C.similar.railFound(load.matches.length);
}

// ---------------------------------------------------------------------------------------------------------------
// Files and links (C-FILE.row)
// ---------------------------------------------------------------------------------------------------------------

/** A row on the page: the server's `FileItem`, or a file that never reached it (kept to try again). */
export interface ProofItem {
  key: string;
  item: FileItem | null;
  /** The browser's copy, kept while it uploads or after it failed, for "Try again". */
  local?: File;
  name: string;
  /** Set by this page when the POST itself failed or was refused. */
  localState?: "uploading" | "upload_failed" | "too_big" | "refused";
  /** The server's words for a refused upload (`too_big`, `type_not_allowed`, `locked`, …), shown under the row. */
  refusal?: string;
  /** What went wrong with this row since: a failed "Hide it for me" or Remove, or Submit's `file_blocked`. */
  note?: string;
  /** Asking for its state kept failing: the row stops asking and offers "Try again" (C-FILE.row). */
  stalled?: boolean;
}

export interface RowView {
  status: FileStatus;
  statusText: string;
  message?: { kind: "error" | "warn"; text: string };
  actions: Array<"view" | "retry" | "hide" | "remove">;
  size?: string;
  kind: string;
  /** The check waits for the gatekeeper (the assistant is off): the row shows the worker's waiting line and no
   * spinner, since nothing moves for hours (WCAG 2.2.2; C-FILE.row, BLD-C237). */
  waiting?: true;
}

export function sizeLabel(bytes: number | undefined): string | undefined {
  if (bytes === undefined || bytes === null || !Number.isFinite(bytes)) return undefined;
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(/\.0$/, "")} MB`;
}

function hostOf(url: string | undefined): string | undefined {
  if (!url) return undefined;
  try {
    return new URL(/^[a-z]+:\/\//i.test(url) ? url : `https://${url}`).host;
  } catch {
    return undefined;
  }
}

/** Part 4's rows for the rail's count (S-05.layout): a link is a link; a file or a folder, or one still uploading,
 * is a file, as Send it's Proof row counts them (BLD-C190). Every row counts, a failed one too, as Review.md's
 * evidence=Upload failed draws it ("2 files"). */
export function proofCounts(proof: ProofItem[]): { files: number; links: number } {
  const links = proof.filter((p) => p.item?.kind === "link").length;
  return { files: proof.length - links, links };
}

/** A row as C-FILE.row draws it, with this page's own note under it and "Try again" once asking has stalled. */
export function rowView(p: ProofItem, limitMb: number): RowView {
  const view = rowBase(p, limitMb);
  if (p.note) view.message = { kind: "error", text: p.note };
  if (p.stalled && !view.actions.includes("retry")) {
    view.actions = [...view.actions.filter((a) => a !== "remove"), "retry", "remove"];
  }
  return view;
}

function rowBase(p: ProofItem, limitMb: number): RowView {
  const item = p.item;
  const ext = p.name.toLowerCase().split(".").pop() ?? "";
  const kind = item?.kind === "link" ? "link" : item?.kind === "folder" ? "folder" : ext;
  const size =
    item?.kind === "link"
      ? hostOf(item.url ?? item.name)
      : sizeLabel(item?.size ?? (p.local ? p.local.size : undefined));
  const state = p.localState ?? item?.state;
  // A checked file, or one found with a detail (DEC-107), opens for the person who added it (A-API.files `view`).
  const view: RowView["actions"] = item?.view_url ? ["view"] : [];
  switch (state) {
    case "uploading":
      return { status: "uploading", statusText: "", actions: ["remove"], size, kind };
    case "checking":
      // While the assistant is off the check waits for the gatekeeper: the worker's line says so (BLD-C225),
      // "Waiting for the personal details check. It runs when the assistant is back." The worker fills `problem`
      // on a checking file only for that wait, so the row drops its spinner then (BLD-C237).
      return {
        status: "checking",
        statusText: item?.problem || C.proof.checking,
        actions: ["remove"],
        size,
        kind,
        ...(item?.problem ? { waiting: true as const } : {}),
      };
    case "checked":
      return { status: "checked", statusText: C.proof.checked, actions: [...view, "remove"], size, kind };
    case "hidden_checked":
      return {
        status: "hidden",
        statusText: item?.hidden_note || C.proof.checked,
        actions: [...view, "remove"],
        size,
        kind,
      };
    case "personal_data_found":
      return {
        status: "found",
        statusText: "",
        message: { kind: "warn", text: item?.problem || C.proof.found },
        actions: [...view, "hide", "remove"],
        size,
        kind,
      };
    case "too_big":
      return {
        status: "too-big",
        statusText: "",
        message: { kind: "error", text: p.refusal || C.proof.tooBig(limitMb) },
        actions: ["remove"],
        size,
        kind,
      };
    case "refused":
      // `type_not_allowed`, `locked`, `forbidden`, `not_found`: the server's words; trying again would not help.
      return {
        status: "failed",
        statusText: "",
        message: { kind: "error", text: p.refusal || C.proof.failed },
        actions: ["remove"],
        size,
        kind,
      };
    case "ok":
    case "unreachable":
      // Links are never fetched (BLD-E001): a link is kept as typed, marked internal or external.
      return {
        status: "checked",
        statusText: item?.link_scope === "internal" ? C.proof.internal : C.proof.external,
        actions: ["remove"],
        size,
        kind: "link",
      };
    case "upload_failed":
    case "infected":
    case "locked":
    default:
      // C-FILE draws no line of its own for `infected` or `locked`: the server's words when it sends them, else the
      // drawn "Didn't upload. Your other files are fine." (BLD-C139).
      return {
        status: "failed",
        statusText: "",
        message: { kind: "error", text: (state !== "upload_failed" && item?.problem) || C.proof.failed },
        actions: state === "upload_failed" ? ["retry", "remove"] : ["remove"],
        size,
        kind,
      };
  }
}

/** Still moving: the page asks again until the file settles, or until asking has stalled. */
export function settling(p: ProofItem): boolean {
  return !p.localState && !p.stalled && (p.item?.state === "uploading" || p.item?.state === "checking");
}

/** Asking for a moving file's state: every 2 s; after a failed ask, twice as long each time up to 30 s; after five
 * failed asks in a row the row offers "Try again" (C-FILE.row, BLD-C139). A file waiting for the gatekeeper (the
 * assistant is off) changes in minutes or hours, not seconds: while every moving file waits, ask every 30 s
 * (BLD-C236). */
export const POLL = { everyMs: 2000, maxMs: 30_000, tries: 5, waitingMs: 30_000 } as const;

/** A file still uploading holds Submit; one still being checked does not (DEC-144 (1), amending L-SUBMIT.pre/3,
 * BLD-B283). The same one state as the server's (`submit/ready.py` `WAITING_FILE`), so the two never disagree: here it
 * is this browser's upload, which the server has no row for until its bytes are stored. */
export function stillUploading(p: ProofItem): boolean {
  return (p.localState ?? p.item?.state) === "uploading";
}

/** A file whose check waits for the gatekeeper: the worker's waiting line is on its checking row (BLD-C225). */
export function waitingForCheck(p: ProofItem): boolean {
  return (p.localState ?? p.item?.state) === "checking" && Boolean(p.item?.problem);
}

export function pollDelay(fails: number, allWaiting = false): number {
  const step = Math.min(POLL.everyMs * 2 ** Math.max(0, fails), POLL.maxMs);
  return allWaiting ? Math.max(step, POLL.waitingMs) : step;
}

/** "Paste a link… Add several links at once with commas." Each piece must look like a link (C-FILE.uploader/3). */
export function splitLinks(text: string): { links: string[]; typed: string[]; bad: boolean } {
  const parts = text
    .split(/[,\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  const looks = (s: string) =>
    /^(https?:\/\/)?[a-z0-9-]+(\.[a-z0-9-]+)+(:\d+)?(\/\S*)?$/i.test(s) && !/@/.test(s.split("/")[0] ?? "");
  const links = parts.filter(looks).map((s) => (/^https?:\/\//i.test(s) ? s : `https://${s}`));
  return { links, typed: parts, bad: parts.length === 0 || links.length !== parts.length };
}

// ---------------------------------------------------------------------------------------------------------------
// The fix sheet (S-05.fix)
// ---------------------------------------------------------------------------------------------------------------

export interface FixForm {
  how: string;
  needs: string;
  solved: string | null;
  measures: Array<"hours" | "cost" | "revenue" | "tools">;
  hours: string;
  cost: string;
  revenue: string;
  basis: string | null;
  risks: string;
}

export const EMPTY_FIX: FixForm = {
  how: "",
  needs: "",
  solved: null,
  measures: [],
  hours: "",
  cost: "",
  revenue: "",
  basis: null,
  risks: "",
};

function worthGiven(f: FixForm): boolean {
  return (
    (f.measures.includes("hours") && f.hours.trim() !== "") ||
    (f.measures.includes("cost") && f.cost.trim() !== "") ||
    (f.measures.includes("revenue") && f.revenue.trim() !== "") ||
    f.measures.includes("tools")
  );
}

/** "2 of 5 ready": how, what it would need, solved already, what it's worth, what that is based on. */
export function fixReady(f: FixForm): number {
  return [
    f.how.trim() !== "",
    f.needs.trim() !== "",
    f.solved !== null,
    worthGiven(f),
    f.basis !== null,
  ].filter(Boolean).length;
}

/** The most useful next answer, in the server's order (services/worker/submit/fix.py NEXT_ORDER). */
export function fixNext(f: FixForm): keyof typeof CHECK_COPY.sheet.next | null {
  if (f.how.trim() === "") return "how";
  if (!worthGiven(f)) return "worth";
  if (f.solved === null) return "solved_already";
  if (f.basis === null) return "basis";
  if (f.needs.trim() === "") return "needs";
  return null;
}

export function fixRequest(f: FixForm, included: boolean): FixRequest {
  const worth: NonNullable<FixRequest["worth"]> = {};
  if (f.measures.includes("hours") && f.hours.trim()) worth.hours_month = f.hours.trim();
  if (f.measures.includes("cost") && f.cost.trim()) worth.cost_month = f.cost.trim();
  if (f.measures.includes("revenue") && f.revenue.trim()) worth.revenue_month = f.revenue.trim();
  if (f.measures.includes("tools")) worth.outside_tools = "partly";
  const out: FixRequest = { included };
  if (f.how.trim()) out.how = f.how.trim();
  if (f.needs.trim()) out.needs = f.needs.trim();
  if (f.solved) out.solved_already = f.solved as FixRequest["solved_already"];
  if (f.basis) out.basis = f.basis as FixRequest["basis"];
  if (f.risks.trim()) out.risks = f.risks.trim();
  if (Object.keys(worth).length) out.worth = worth;
  return out;
}

/** The sheet filled from what was saved before ("Change", "Carry on with your fix"). */
export function fixFormFrom(fix: (Partial<FixRequest> & { worth?: unknown }) | null | undefined): FixForm {
  if (!fix) return EMPTY_FIX;
  const w = (fix.worth ?? {}) as Record<string, unknown>;
  const text = (v: unknown) =>
    typeof v === "string"
      ? v
      : v && typeof v === "object" && "text" in v
        ? String((v as { text: unknown }).text)
        : "";
  const measures: FixForm["measures"] = [];
  if (w.hours_month) measures.push("hours");
  if (w.cost_month) measures.push("cost");
  if (w.revenue_month) measures.push("revenue");
  if (w.outside_tools === "partly" || w.outside_tools === "fully") measures.push("tools");
  return {
    how: fix.how ?? "",
    needs: fix.needs ?? "",
    solved: fix.solved_already ?? null,
    measures,
    hours: text(w.hours_month),
    cost: text(w.cost_month),
    revenue: text(w.revenue_month),
    basis: fix.basis ?? null,
    risks: fix.risks ?? "",
  };
}

/** "Send the reason in plain words…": the fix in one line, as the server cuts it (fix.py one_line). */
export function oneLine(how: string): string {
  const text = how.split(/\s+/).filter(Boolean).join(" ");
  return text.length <= 140 ? text : `${text.slice(0, 139).trimEnd()}…`;
}
