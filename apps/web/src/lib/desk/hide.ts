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
/** Said to a screen reader when "Hide this" appears after a selection: it is next in Tab order (WCAG 4.1.3). */
export const HIDE_NEXT = "Hide this is next. Press Tab.";
export const HIDE_WORDS = {
  range_invalid: "Select at least 3 letters or numbers.",
  already_hidden: "That’s already hidden.",
  /** The text changed under the selection (another reviewer hid something): the page is read again (BLD-B247). */
  stale: "The page changed. Select again.",
} as const;

/** The line under "Hide this" when the hide is refused: plain words per code, else F-COPY's failure line. */
export function hideErrorWords(code: string): string {
  return code === "range_invalid" || code === "already_hidden" || code === "stale"
    ? HIDE_WORDS[code]
    : TRY_AGAIN;
}

/** A text's name for a screen reader when it takes focus: "The problem, text" (WCAG 4.1.2; BLD-B247). */
export function hideableName(what: string): string {
  return `${what}, text`;
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

/** A selection in one source's text: UTF-16 offsets and the selected words as the page shows them (masked). */
export interface Selected {
  start: number;
  end: number;
  selected: string;
}

/**
 * The selection's offsets in its source's `text`, in UTF-16 units as the browser counts them. `before` is the text
 * from the source's start to the selection's start, `selected` the selected text. Spaces at either end are left out
 * (a double-click takes the space after a word). Null when the selection is not part of `text` or holds only spaces.
 */
export function selectionOffsets(text: string, before: string, selected: string): Selected | null {
  let start = before.length;
  let end = start + selected.length;
  if (!selected || text.slice(start, end) !== selected) return null;
  while (start < end && /\s/.test(text.charAt(start))) start += 1;
  while (end > start && /\s/.test(text.charAt(end - 1))) end -= 1;
  return end > start ? { start, end, selected: text.slice(start, end) } : null;
}

/** The same, for a DOM range inside the element that holds exactly the source's text. */
export function rangeOffsets(host: Node, range: Range): Selected | null {
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

/**
 * The body for lane C's route. `selected` is the masked words the reviewer selected, so the worker can refuse with
 * `stale` when its text no longer has them at those offsets (lane C's next hide round; it ignores the field until
 * then, BLD-B247).
 */
export function hideBody(source: HideSource, at: Selected) {
  return { source, start: at.start, end: at.end, units: "utf16" as const, selected: at.selected };
}

/** Keyboard selection inside a focused text (WCAG 2.1.1): Shift and an arrow, Home or End extend it. */
export interface ExtendStep {
  direction: "forward" | "backward";
  granularity: "character" | "word" | "line" | "lineboundary";
}

interface KeyLike {
  key: string;
  code?: string;
  shiftKey: boolean;
  altKey: boolean;
  ctrlKey: boolean;
  metaKey: boolean;
}

/** What Shift and a key does to the selection: a letter (a word with Ctrl, or Option on a Mac), a line, to a line's end. */
export function extendStep(e: KeyLike): ExtendStep | null {
  if (!e.shiftKey || e.metaKey) return null;
  const word = e.ctrlKey || e.altKey;
  switch (e.key) {
    case "ArrowRight":
      return { direction: "forward", granularity: word ? "word" : "character" };
    case "ArrowLeft":
      return { direction: "backward", granularity: word ? "word" : "character" };
    case "ArrowDown":
      return { direction: "forward", granularity: "line" };
    case "ArrowUp":
      return { direction: "backward", granularity: "line" };
    case "End":
      return { direction: "forward", granularity: "lineboundary" };
    case "Home":
      return { direction: "backward", granularity: "lineboundary" };
    default:
      return null;
  }
}

/** Enter, or Alt+H (Option+H on a Mac types "˙", so the key's code is read), moves to "Hide this". */
export function opensHide(e: KeyLike): boolean {
  if (e.metaKey || e.ctrlKey) return false;
  if (e.key === "Enter" && !e.altKey && !e.shiftKey) return true;
  return e.altKey && !e.shiftKey && (e.code === "KeyH" || e.key.toLowerCase() === "h");
}
