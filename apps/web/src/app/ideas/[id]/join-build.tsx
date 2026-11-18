"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import type { JoinBuild } from "@/lib/contracts";

import type { Decided } from "./decision";

const ASK = "Ask to join the build team";

/**
 * Lane B's `join_build` on the decision, read defensively: null for anyone but the sharer and an active crew member,
 * and until lane B's endpoint is on the page's data (then S-06 shows nothing for it).
 */
export function joinBuildOf(d: Decided | null): JoinBuild | null {
  const raw = (d as { join_build?: unknown } | null)?.join_build;
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const text = (v: unknown) => (typeof v === "string" && v ? v : null);
  return { can_ask: o.can_ask === true, asked_at: text(o.asked_at), reply_by: text(o.reply_by) };
}

/** "27 November": the day and the month, in office time (India). null when there is no date or it can't be read. */
export function dayMonth(iso: string | null): string | null {
  if (!iso) return null;
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return null;
  return new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", day: "numeric", month: "long" }).format(
    t,
  );
}

/** Status.dc.html:899, PhoneStatus.dc.html:889; the date is the Pick's team-chosen-by date, lane B's `reply_by`. */
export function askedLine(replyBy: string | null): string {
  const by = dayMonth(replyBy);
  // NOT DRAWN (BLD-E055): without a reply-by date the date clause goes; HR sign-off
  return by ? `Asked. The build lead replies by ${by}.` : "Asked. The build lead replies.";
}

/**
 * S-06's "Ask to join the build team" after a Pick (L-DECIDE/6, A-API `POST /ideas/:id/join-build`; J-REVIEW/6). The
 * button shows while lane B says the sharer can ask; once asked it gives way to the drawn line, with no Undo: A-API has
 * no way to take the ask back (BLD-E055). A refusal shows the screen's own "try again" line and refreshes the page,
 * so a button that no longer applies goes.
 */
export function AskToJoin({
  ideaId,
  d,
  failed,
  away,
}: {
  ideaId: string;
  d: Decided;
  /** The screen's TRY_AGAIN line under the card. */
  failed: (on: boolean) => void;
  /** Where focus goes if the button leaves after a refusal: the idea's title, as after Withdraw and Restore. */
  away: () => void;
}) {
  const router = useRouter();
  const join = joinBuildOf(d);
  const [busy, setBusy] = useState(false);
  const [askedAt, setAskedAt] = useState<string | null>(null);
  const line = useRef<HTMLParagraphElement>(null);
  // After the click focus goes to the line that replaced the button, or, when a refusal's refresh took the button
  // away, to the title, so a keyboard user is never left on the page's body; a button that stays keeps its focus
  const next = useRef<"line" | "away" | null>(null);

  const standing = d.decision.choice === "pick" && !d.reversal && d.window?.state !== "reversed";
  const asked = askedAt ?? join?.asked_at ?? null;
  const show: "line" | "button" | null =
    !standing || (!join && !askedAt) ? null : asked ? "line" : join?.can_ask ? "button" : null;

  useEffect(() => {
    if (next.current === "line" && show === "line") {
      next.current = null;
      line.current?.focus();
    } else if (next.current === "away" && show !== "button") {
      next.current = null;
      const at = document.activeElement;
      if (!at || at === document.body) away();
    }
  });

  const ask = async () => {
    setBusy(true);
    failed(false);
    next.current = null;
    try {
      const res = await fetch(`/api/ideas/${encodeURIComponent(ideaId)}/join-build`, { method: "POST" });
      if (!res.ok) throw new Error(String(res.status));
      const body = (await res.json().catch(() => null)) as { asked_at?: unknown } | null;
      const at =
        typeof body?.asked_at === "string" && body.asked_at ? body.asked_at : new Date().toISOString();
      next.current = "line";
      // The line takes focus, which reads it out; it is not also put in the status line, so it is heard once
      setAskedAt(at);
    } catch {
      next.current = "away";
      failed(true);
      router.refresh();
    } finally {
      setBusy(false);
    }
  };

  if (!show) return null;
  return (
    <div className="ip-card-acts">
      {show === "line" ? (
        <p ref={line} tabIndex={-1} className="ip-joined">
          <svg width="14" height="14" viewBox="0 0 12 12" fill="none" aria-hidden="true" focusable="false">
            <path
              d="M2.5 6.2 5 8.5l4.5-5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          {askedLine(join?.reply_by ?? null)}
        </p>
      ) : (
        // The board's `btn line`; on S-06's dark card the line buttons are `soft`, as "Open IDEA-…" is (BLD-E055)
        <Button variant="soft" disabled={busy} onClick={() => void ask()}>
          {ASK}
        </Button>
      )}
    </div>
  );
}
