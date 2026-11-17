"use client";

/**
 * C-QCARD: the review desk's questions everywhere except the Answer screen: a card with one button, never a text
 * box. Placed by other lanes: Home's "Needs you" (compact), the sharer's idea page (S-06), the conversation (S-08)
 * and the Inbox reader (S-H5). Feed it the sharer's open set from `GET /api/ideas/{id}/question-set`.
 */
import { useEffect, useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { ButtonLink } from "@/components/ui/button";
import { Pill } from "@/components/ui/pill";
import type { SharerQuestionSetResponse } from "@/lib/contracts";
import { countdown, countdownLabel, nextTickMs } from "@/lib/desk/countdown";
import { CUSTOMER_DETAIL } from "@/lib/desk/files";
import { clockLabel, dayLabel } from "@/lib/desk/when";

import "./qcard.css";

type Set = NonNullable<SharerQuestionSetResponse>;

function useMinute(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    const tick = () => {
      setNow(new Date());
      t = setTimeout(tick, nextTickMs());
    };
    t = setTimeout(tick, nextTickMs());
    return () => clearTimeout(t);
  }, []);
  return now;
}

export function QuestionsCard({
  ideaId,
  set,
  compact = false,
}: {
  ideaId: string;
  set: Set;
  compact?: boolean;
}) {
  const now = useMinute();
  const who = set.by.first_name;
  const sent = set.sent_at ? `${dayLabel(set.sent_at, now)}, ${clockLabel(set.sent_at)}` : "";
  const answered = set.state === "answered";
  const partly = !answered && set.answered > 0;
  const live = set.due_at && !answered ? countdown(set.due_at, now) : null;
  const href = `/ideas/${encodeURIComponent(ideaId)}/answer`;
  const n = set.count;

  return (
    <article className={`card qcard${compact ? " qcard-compact" : ""}`} aria-labelledby={`qcard-${set.id}`}>
      <header className="qcard-h">
        <Avatar initials={set.by.initials} size={32} name={set.by.name} />
        <span className="meta">
          {who} from the review desk, {sent}
        </span>
        {answered ? (
          <Pill variant="ok">Answered</Pill>
        ) : live ? (
          <Pill variant={live.variant === "normal" ? "neutral" : live.variant}>
            {countdownLabel(live, "left")}
          </Pill>
        ) : null}
      </header>
      <h3 id={`qcard-${set.id}`} className="h3">
        {answered
          ? `${who}’s ${n} question${n === 1 ? "" : "s"}, answered`
          : `${who} has ${n} question${n === 1 ? "" : "s"} for you`}
      </h3>
      {answered && set.answered_at ? (
        <p className="meta">
          Answered on {dayLabel(set.answered_at, now)}, {clockLabel(set.answered_at)}. Your answers are below,
          each added to its part of your idea.
        </p>
      ) : null}
      {compact ? null : (
        <ol className="qcard-list">
          {set.questions.map((q) => (
            <li key={q.id} className={q.answer?.sent ? "done" : undefined}>
              {/* Partly answered (NOT DRAWN): an answered question shows a tick beside its words */}
              <p className="body">
                {q.answer?.sent && !answered ? (
                  <span className="qcard-tick" role="img" aria-label="Answered">
                    ✓{" "}
                  </span>
                ) : null}
                {q.text}
              </p>
              <p className="meta">
                {answered ? "Added to" : "Answer goes to"} {q.part_name}
              </p>
              {answered && q.answer ? <p className="body qcard-a">{q.answer.text}</p> : null}
              {answered && q.answer?.files.length ? (
                <ul className="qcard-files" aria-label="Files with this answer">
                  {q.answer.files.map((f) => (
                    <li key={f.id} className="meta">
                      {f.name}
                      {f.hidden_note ? `. ${f.hidden_note}` : ""}
                      {f.customer_detail ? (
                        <>
                          {" "}
                          <Pill variant="warn">{CUSTOMER_DETAIL}</Pill>
                        </>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ol>
      )}
      {answered ? null : (
        <footer className="qcard-f">
          <p className="meta">{set.deadline}. One at a time, typed or spoken.</p>
          <ButtonLink href={href} variant="primary" size="sm">
            {partly ? "Carry on answering" : "Answer the questions"}
          </ButtonLink>
        </footer>
      )}
    </article>
  );
}
