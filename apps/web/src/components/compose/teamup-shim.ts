"use client";
/**
 * A stand-in for lane F's team-up sheet (C-SHEET-TEAMUP) until it is on main (BLD-C129). Same signature as
 * `useTeamUpSheet` in `@/components/teamup/teamup-sheet` (f/sheet-teamup-2 at 37acc2e), so S-04B's similar strip is
 * wired the way it will run: `onPrimary={teamUp.open}` on C-PREVIEW and `{teamUp.sheet}` in the page. Until then
 * the sheet draws nothing. When lane F says team-up is on main, the one import in `app/share/compose.tsx` swaps to
 * "@/components/teamup/teamup-sheet" and this file goes. Never create anything under components/teamup/.
 */
import { createElement, Fragment, useCallback, useState, type JSX } from "react";

/** What the opener is told after a send (lane F's `TeamUpSent`). */
export interface TeamUpSent {
  kind: "teamup" | "merge";
  id: string;
  ideaId: string;
  note: string;
  brought: string[];
  /** What the opener shows now, "Waiting for Ravi" (C-SHEET-TEAMUP.after). */
  after: {
    state: string;
    line: string;
    label?: string;
    detail?: string;
    action?: { label: string; op?: string; to?: string } | null;
    can_submit?: boolean;
  } | null;
}

export interface TeamUpSheetOptions {
  onSent?(sent: TeamUpSent): void;
  onWithdrawn?(sent: TeamUpSent): void;
  /** The person's unsent draft: turns on "bring my draft" (L-MERGE.request/1). */
  draftId?: string;
  draftTitle?: string;
  doneLabel?: "Done" | "Keep looking";
  me?: { initials: string };
  onClose?(): void;
  /** Where focus goes on close when the opener is gone; without it, the element marked `teamUpOpener` (BLD-F074). */
  returnFocus?(): HTMLElement | null | undefined;
}

/** Spread on whatever stands where "Team up" was, so focus can return to it when the sheet closes (WCAG 2.4.3). */
export function teamUpOpener(ideaId: string): { "data-teamup-opener": string } {
  return { "data-teamup-opener": ideaId };
}

export function useTeamUpSheet(options: TeamUpSheetOptions = {}): {
  open(ideaId: string): void;
  close(): void;
  isOpen: boolean;
  sheet: JSX.Element;
} {
  void options;
  const [ideaId, setIdeaId] = useState<string | null>(null);
  const open = useCallback((id: string) => setIdeaId(id), []);
  const close = useCallback(() => setIdeaId(null), []);
  return { open, close, isOpen: ideaId !== null, sheet: createElement(Fragment) };
}
