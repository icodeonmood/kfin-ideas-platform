/**
 * S-R2 "Hide this" (L-HIDE.rules/7, BLD-B246): a reviewer selects words the checks missed in what they read, and lane
 * C's `POST /api/desk/ideas/:id/hide` masks them at once in every copy and tells the sharer (`detail_hidden_by_desk`,
 * posted by the worker; this side posts nothing). The offsets are the browser's (UTF-16 units) in the text of one
 * source, exactly as the page shows it; the worker converts them against the same text.
 */
import type { IdeaPart } from "@/lib/contracts";

import { TRY_AGAIN } from "./reply";

/** Lane C's source kinds (`DESK_SOURCE_KINDS` in server/hide.ts). */
export type HideSourceKind = "part" | "message" | "answer" | "title" | "conversation" | "fix";
export interface HideSource {
  kind: HideSourceKind;
  id: string;
}

export const HIDE_THIS = "Hide this";
/** Said to a screen reader once the words are hidden (C-HIDDEN's "Hidden from everyone"). */
export const HIDDEN_DONE = "Hidden from everyone.";
export const HIDE_WORDS = {
  range_invalid: "Select at least 3 letters or numbers.",
  already_hidden: "That’s already hidden.",
} as const;

/** The line under "Hide this" when the hide is refused: plain words per code, else F-COPY's failure line. */
export function hideErrorWords(code: string): string {
  return code === "range_invalid" || code === "already_hidden" ? HIDE_WORDS[code] : TRY_AGAIN;
}

/**
 * Where a part's words are kept, for the parts whose shown text is one stored text: the problem, how often (columns
 * of the idea, lane C's "title" kind) and the fix (`idea_fix.how`). Who it affects, what it's worth and the attached
 * part are put together for the page, so they are not offered (BLD-B246).
 */
export function partSource(part: IdeaPart): HideSource | null {
  if (part === "summary") return { kind: "title", id: "summary" };
  if (part === "often") return { kind: "title", id: "often" };
  if (part === "fix") return { kind: "fix", id: "how" };
  return null;
}

/**
 * The selection's offsets in its source's `text`, in UTF-16 units as the browser counts them. `before` is the text
 * from the source's start to the selection's start, `selected` the selected text. Spaces at either end are left out
 * (a double-click takes the space after a word). Null when the selection is not part of `text` or holds only spaces.
 */
export function selectionOffsets(
  text: string,
  before: string,
  selected: string,
): { start: number; end: number } | null {
  let start = before.length;
  let end = start + selected.length;
  if (!selected || text.slice(start, end) !== selected) return null;
  while (start < end && /\s/.test(text.charAt(start))) start += 1;
  while (end > start && /\s/.test(text.charAt(end - 1))) end -= 1;
  return end > start ? { start, end } : null;
}

/** The same, for a DOM range inside the element that holds exactly the source's text. */
export function rangeOffsets(host: Node, range: Range): { start: number; end: number } | null {
  if (!host.contains(range.startContainer) || !host.contains(range.endContainer)) return null;
  const doc = host.ownerDocument;
  if (!doc) return null;
  const head = doc.createRange();
  head.selectNodeContents(host);
  head.setEnd(range.startContainer, range.startOffset);
  return selectionOffsets(host.textContent ?? "", head.toString(), range.toString());
}

export function hideUrl(ideaId: string): string {
  return `/api/desk/ideas/${encodeURIComponent(ideaId)}/hide`;
}

export function hideBody(source: HideSource, at: { start: number; end: number }) {
  return { source, start: at.start, end: at.end, units: "utf16" as const };
}
