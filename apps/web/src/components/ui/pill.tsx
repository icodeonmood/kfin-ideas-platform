import type { ReactNode } from "react";

/**
 * C-PILL: a status as a dot and words, never the dot alone. Which status takes which colour is fixed by
 * E-ENUMS.idea-status, not chosen per screen: use StatusPill for an idea's status.
 */
export type PillVariant = "neutral" | "blue" | "ok" | "warn" | "bad" | "band" | "soon";

export function Pill({ variant = "neutral", children }: { variant?: PillVariant; children: ReactNode }) {
  return (
    <span className={variant === "neutral" ? "pill" : `pill ${variant}`}>
      {variant === "soon" ? null : <i aria-hidden="true" />}
      {children}
    </span>
  );
}

/** E-ENUMS.idea-status: the statuses an idea can show, their words and their pill. */
export const IDEA_STATUS = {
  draft: { label: "Draft", pill: "neutral" },
  checking: { label: "Checking", pill: "blue" },
  with_review_desk: { label: "With the review desk", pill: "blue" },
  needs_you: { label: "Needs you", pill: "warn" },
  picked: { label: "Picked", pill: "blue" },
  being_built: { label: "Being built", pill: "blue" },
  shipped: { label: "Shipped", pill: "ok" },
  not_now: { label: "Not now", pill: "warn" },
  not_picked: { label: "Not picked", pill: "neutral" },
  withdrawn: { label: "Withdrawn", pill: "neutral" },
  merged: { label: "Merged", pill: "neutral" },
} as const satisfies Record<string, { label: string; pill: PillVariant }>;

export type IdeaStatus = keyof typeof IDEA_STATUS;

export function StatusPill({ status }: { status: IdeaStatus }) {
  const s = IDEA_STATUS[status];
  return <Pill variant={s.pill}>{s.label}</Pill>;
}
