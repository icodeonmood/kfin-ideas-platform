/**
 * S-05's rules that need no screen: which part comes next, what each rail row says, how a file's state reads
 * (C-FILE.row), what a similar idea's tile shows after a request (C-SIMGRID.tile), and how ready a fix is
 * (S-05.fix). Pure functions, so the vitest suite covers them without a browser.
 */
import type { FileStatus } from "@/components/ui/file";
import type { DraftStep, FileItem, FixRequest, SimilarMatch } from "@/lib/contracts";

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
    if (!merge || merge.state !== "waiting" || !merge.other_idea_id) return null;
    // NOT DRAWN by the route: compose the drawn lines from the lead's first name.
    const lead = merge.lead ?? matches.find((m) => m.idea.id === merge.other_idea_id)?.idea.lead;
    const first = firstName(lead);
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

/** A tile's action row (C-SIMGRID.tile): "Team up", "Waiting for Ravi" + "Withdraw", or "On the crew". */
export type TileAction =
  | { kind: "team-up" }
  | { kind: "waiting"; label: string; withdraw: { merge: true } | { requestId: string } }
  | { kind: "on-crew" };

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
}

export interface RowView {
  status: FileStatus;
  statusText: string;
  message?: { kind: "error" | "warn"; text: string };
  actions: Array<"view" | "retry" | "hide" | "remove">;
  size?: string;
  kind: string;
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

export function rowView(p: ProofItem, limitMb: number): RowView {
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
      return { status: "checking", statusText: C.proof.checking, actions: ["remove"], size, kind };
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
      return {
        status: "failed",
        statusText: "",
        message: { kind: "error", text: C.proof.failed },
        actions: state === "upload_failed" ? ["retry", "remove"] : ["remove"],
        size,
        kind,
      };
  }
}

/** Still moving: the page asks again until the file settles. */
export function settling(p: ProofItem): boolean {
  return !p.localState && (p.item?.state === "uploading" || p.item?.state === "checking");
}

/** "Paste a link… Add several links at once with commas." Each piece must look like a link (C-FILE.uploader/3). */
export function splitLinks(text: string): { links: string[]; bad: boolean } {
  const parts = text
    .split(/[,\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  const looks = (s: string) =>
    /^(https?:\/\/)?[a-z0-9-]+(\.[a-z0-9-]+)+(:\d+)?(\/\S*)?$/i.test(s) && !/@/.test(s.split("/")[0] ?? "");
  const links = parts.filter(looks).map((s) => (/^https?:\/\//i.test(s) ? s : `https://${s}`));
  return { links, bad: parts.length === 0 || links.length !== parts.length };
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
