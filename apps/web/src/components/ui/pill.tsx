import type { ReactNode } from "react";

/**
 * C-PILL: a status as a dot and words, never the dot alone. Which status takes which colour is fixed by
 * E-ENUMS.idea-status, not chosen per screen: use StatusPill for an idea's status.
 */
export type PillVariant = "neutral" | "blue" | "ok" | "warn" | "bad" | "band" | "soon" | "latest";

/** C-PILL.rules/3, S-R1.layout/4: a countdown's look on the board (Desk `.due`) for the variant a screen picks. Warn is
 * under a day ("soon"), bad is overdue and solid ("over"), ok is a closed clock ("done"); anything else is neutral. */
const COUNTDOWN: Partial<Record<PillVariant, string>> = { warn: "soon", bad: "over", ok: "done" };

function ClockIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="13" r="8" />
      <path d="M12 9v4l2.5 2M9.5 2.5h5" />
    </svg>
  );
}

/** `countdown` draws a clock in place of the dot, in the board's countdown looks ("3 days to answer"). */
export function Pill({
  variant = "neutral",
  countdown = false,
  children,
}: {
  variant?: PillVariant;
  countdown?: boolean;
  children: ReactNode;
}) {
  if (countdown) {
    const look = COUNTDOWN[variant];
    return (
      <span className={look ? `due ${look}` : "due"}>
        <ClockIcon />
        {children}
      </span>
    );
  }
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
