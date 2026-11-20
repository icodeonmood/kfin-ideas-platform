"use client";

/**
 * "Requested" with "Withdraw" (DEC-126, walk item WF-03b; BLD-F094): what stands where "Team up" was on a crew card
 * once the person has asked to join the idea. Find your crew (S-H2) draws it on its cards; Home's crew card (S-03,
 * lane C) drops it in the same way.
 *
 * - "Requested" is the host's own "Team up" button, greyed and inactive: `aria-disabled="true"` (never `disabled`),
 *   so it stays focusable and is read out as its state, and clicks do nothing. An inactive control may sit below
 *   4.5:1. It carries `teamUpOpener(ideaId)`, so the sheet's focus comes back to it when the host re-drew "Team up"
 *   as "Requested" while the sheet was open (WCAG 2.4.3).
 * - "Withdraw" is its own control under the button, never inside it: grey, sub-text size and weight, underlined, at
 *   4.5:1 or better on the card, with the shared focus ring. It calls `DELETE /api/team-up/:id` with the card's
 *   request id (either kind) and then `onWithdrawn`. The host draws "Team up" again in the same place, marked with
 *   `teamUpOpener(ideaId)`, and focus moves there; that announces the change, so the pair needs no live region.
 *
 * Styles: the class names are lane D's shared ones (`is-inactive` on the button, `link-quiet` on the link,
 * BLD-D019). Until BLD-D019 is on `main` they are drawn for S-H2 only, in `app/crew/crew.css`; a host elsewhere needs
 * lane D's shared copy (the button already greys through its own `aria-disabled` look).
 *
 * Privacy: the request id is the viewer's own; nothing else about the request is read or shown, and nothing is
 * logged (non-negotiable 3).
 */
import { useRef, useState, type JSX } from "react";

import { Button, type ButtonSize, type ButtonVariant } from "@/components/ui/button";
import { FieldMsg } from "@/components/ui/field";
import type { CrewCardRequest } from "@/lib/contracts/entities";

import {
  markedOpener,
  TEAMUP_COPY,
  teamUpOpener,
  withdrawRequest,
  type SheetError,
  type TeamUpSent,
} from "./teamup-sheet";

/** The words (DEC-126: "Requested" and "Withdraw" are the product lead's; the names are in docs/hr-wording/lane-f.md). */
export const REQUESTED_COPY = {
  requested: "Requested",
  /** NOT DRAWN: what a screen reader hears for "Requested"; it starts with the visible word (WCAG 2.5.3). */
  requestedOn: (title: string) => `Requested: you asked to team up on ${title}`,
  withdraw: "Withdraw",
  /** NOT DRAWN: what a screen reader hears for "Withdraw"; it starts with the visible word (WCAG 2.5.3). */
  withdrawOn: (title: string) => `Withdraw your request to team up on ${title}`,
  withdrawing: TEAMUP_COPY.withdrawing,
} as const;

export interface RequestedActionProps {
  /** The idea asked about, its reference (IDEA-2026-001412). */
  ideaId: string;
  /** The idea's title, for the two controls' names ("Requested: you asked to team up on …"). */
  title?: string;
  /** The card's waiting request (`CrewCard.request`, or `{ id, kind }` from `TeamUpSent` after a send). */
  request: CrewCardRequest;
  /**
   * After a withdraw: the host drops the card's request and draws "Team up" again in the same place, marked with
   * `teamUpOpener(ideaId)`; the card does not move. Called with the same `TeamUpSent` the sheet's `onWithdrawn` gets
   * (`note` and `brought` empty).
   */
  onWithdrawn(sent: TeamUpSent): void;
  /** The host's "Team up" variant and size, so "Requested" stands exactly where it was. */
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Extra classes on "Requested" (the host's "Team up" classes). */
  className?: string;
}

export function RequestedAction({
  ideaId,
  title,
  request,
  onWithdrawn,
  variant = "primary",
  size = "full",
  className,
}: RequestedActionProps): JSX.Element {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<SheetError | null>(null);
  const link = useRef<HTMLButtonElement>(null);

  const withdraw = async () => {
    if (busy || !request.id) return;
    setBusy(true);
    setError(null);
    const r = await withdrawRequest(request.id);
    setBusy(false);
    if (!r.ok) {
      setError(r.error);
      return;
    }
    onWithdrawn({ kind: request.kind, id: request.id, ideaId, note: "", brought: [], after: r.after });
    // Once the host has drawn "Team up" again, focus goes to it (WCAG 2.4.3). A host that keeps this pair keeps focus.
    requestAnimationFrame(() => {
      if (link.current?.isConnected) return;
      markedOpener(ideaId)?.focus({ preventScroll: true });
    });
  };

  return (
    <div className="tu-req">
      <Button
        variant={variant}
        size={size}
        className={["is-inactive", className].filter(Boolean).join(" ")}
        disabled
        aria-label={title ? REQUESTED_COPY.requestedOn(title) : undefined}
        {...teamUpOpener(ideaId)}
      >
        {REQUESTED_COPY.requested}
      </Button>
      {/* A reply with no request id leaves nothing to withdraw (BLD-F074). */}
      {request.id ? (
        <button
          ref={link}
          type="button"
          className="link-quiet"
          aria-label={title && !busy ? REQUESTED_COPY.withdrawOn(title) : undefined}
          aria-busy={busy ? true : undefined}
          onClick={() => void withdraw()}
        >
          {busy ? REQUESTED_COPY.withdrawing : REQUESTED_COPY.withdraw}
        </button>
      ) : null}
      {error ? <FieldMsg>{error.message}</FieldMsg> : null}
    </div>
  );
}
