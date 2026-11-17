"use client";

/**
 * A typed stand-in for lane F's team-up sheet (C-SHEET-TEAMUP, `@/components/teamup/teamup-sheet`, on
 * f/sheet-teamup-2), so this branch builds before team-up reaches main. Same signature as lane F's
 * `useTeamUpSheet`; it renders nothing and opens nothing. When lane F says team-up is on main, the one import line
 * in similar.tsx swaps to "@/components/teamup/teamup-sheet" and this file goes (lane F's request: nothing of lane
 * C's under components/teamup/).
 */
import { useCallback, useState, type JSX } from "react";

/** Lane F's `TeamUpAfter`: what the screen that opened the sheet shows now (C-SHEET-TEAMUP.after). */
export interface TeamUpAfter {
  state: string;
  line: string;
  label?: string;
  detail?: string;
  action?: { label: string; op?: string; to?: string } | null;
  can_submit?: boolean;
}

/** Lane F's `TeamUpSent`: what the opener is told after a send or a withdraw. */
export interface TeamUpSent {
  kind: "teamup" | "merge";
  id: string;
  ideaId: string;
  note: string;
  brought: string[];
  after: TeamUpAfter | null;
}

export interface TeamUpSheetOptions {
  onClose?(): void;
  onSent?(sent: TeamUpSent): void;
  onWithdrawn?(sent: TeamUpSent): void;
  draftId?: string;
  draftTitle?: string;
  doneLabel?: "Done" | "Keep looking";
  me?: { initials: string };
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
  return { open, close, isOpen: ideaId !== null, sheet: <></> };
}
