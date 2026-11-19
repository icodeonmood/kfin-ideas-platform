"use client";

/**
 * Flag S2 "Check first" on a phone (P-DECISIONS.experiments, L-SIMILAR "Flag S2"; PhoneReview.md, `simulatorS2=Check
 * first`; BLD-C176): with a close match, Check it opens on the comparison before the rest of the page. Yours, not
 * sent yet, beside the close idea (its reference and the day it was shared, the masked one-sentence summary, area,
 * city and crew count; never anyone's raw words, non-negotiable 7); the next match named in one line if it is only
 * related. The dock holds "Team up", which opens lane F's sheet on the close idea with this draft (C-SHEET-TEAMUP),
 * and "Mine is different", which carries on to the rest of Check it and records nothing about the idea.
 */
import { useId } from "react";

import { Dock } from "@/components/shell/phone";
import { teamUpOpener, useTeamUpSheet, type TeamUpSent } from "@/components/teamup/teamup-sheet";
import { Button } from "@/components/ui/button";
import { FieldMsg } from "@/components/ui/field";
import type { SimilarMatch } from "@/lib/contracts";

import { CHECK_COPY } from "./copy";

const C = CHECK_COPY.checkFirst;
const Y = CHECK_COPY.similar;

/** "9 November": the day an idea was shared, in India time. */
export function sharedDay(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "long", timeZone: "Asia/Kolkata" });
}

export function CheckFirstPhone({
  draftId,
  draftTitle,
  draftSummary,
  close,
  next,
  onSent,
  onWithdrawn,
  onDifferent,
  error = null,
}: {
  draftId: string;
  draftTitle: string;
  draftSummary: string;
  /** The top match, `close` (strongMatch). */
  close: SimilarMatch;
  /** The match after it, named only when it is `related` (as drawn). */
  next: SimilarMatch | null;
  onSent(sent: TeamUpSent): void;
  onWithdrawn(): void;
  onDifferent(): void;
  /** A team-up that could not be recorded: its words, under the comparison. */
  error?: string | null;
}) {
  const id = useId();
  const teamUp = useTeamUpSheet({ onSent, onWithdrawn, draftId, draftTitle });
  const idea = close.idea;
  const day = sharedDay(idea.shared_at);
  const related = next && next.strength === "related" ? next.idea : null;
  return (
    <section className="ck-first" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`} className="h2 ck-h" tabIndex={-1}>
        {C.heading}
      </h2>
      {day ? <p className="ck-line">{C.line(day)}</p> : null}
      <div className="ck-first-cards">
        <div className="sgt yours">
          <div className="sgt-top">
            <span className="ck-yours">{Y.yours}</span>
          </div>
          <p className="sgt-t">{draftTitle}</p>
          {draftSummary ? <p className="sgt-s">{draftSummary}</p> : null}
        </div>
        <div className="sgt ck-first-close">
          <p className="meta">{day ? C.ref(idea.id, day) : idea.id}</p>
          <h3 className="sgt-t">{idea.title}</h3>
          {idea.in_their_words ? <p className="sgt-s">{idea.in_their_words}</p> : null}
          <p className="meta">{C.where(idea.area, idea.city, idea.crew_count)}</p>
        </div>
      </div>
      {error ? <FieldMsg>{error}</FieldMsg> : null}
      {related ? (
        <p className="meta ck-first-also">{C.alsoRelated(related.title, related.area, related.city)}</p>
      ) : null}
      {/* As drawn: "Team up" on top, "Mine is different" under it, in that order for the keyboard too. */}
      <Dock>
        <div className="ck-first-dock">
          <Button {...teamUpOpener(idea.id)} size="full" onClick={() => teamUp.open(idea.id)}>
            {C.teamUp}
          </Button>
          <Button variant="text" onClick={onDifferent}>
            {C.different}
          </Button>
        </div>
      </Dock>
      {teamUp.sheet}
    </section>
  );
}
