"use client";

/**
 * C-QCARD: the review desk's questions everywhere except the Answer screen: a card with one button, never a text
 * box. Placed by other lanes, each with its board's words (C-QCARD.places): `variant="status"` on the sharer's idea
 * page (S-06, Status.md) and the conversation (S-08), `"home"` in Home's "Needs you" (S-03, Home.md) and `"inbox"`
 * in the Inbox reader (S-H5, Inbox.md). Feed it the sharer's open set from `GET /api/ideas/{id}/question-set`.
 * In the reader the card is the item's body: the reader keeps its own header and pins the button to its foot
 * (S-H5.layout, S-H5.rules/3), with the words `answerLabel` gives.
 */
import Link from "next/link";
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

export type QuestionsCardVariant = "status" | "home" | "inbox";

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

/** The card's one button (C-QCARD.anatomy/5, .states): "Answer the questions", "Carry on answering" once some are
 * sent, none once every question is answered. */
export function answerLabel(set: Pick<Set, "state" | "answered">): string | null {
  if (set.state === "answered") return null;
  return set.answered > 0 ? "Carry on answering" : "Answer the questions";
}

/** Where the button goes: the Answer screen (S-R3). */
export function answerHref(ideaId: string): string {
  return `/ideas/${encodeURIComponent(ideaId)}/answer`;
}

export function QuestionsCard({
  ideaId,
  set,
  variant = "status",
}: {
  ideaId: string;
  set: Set;
  variant?: QuestionsCardVariant;
}) {
  const now = useMinute();
  const who = set.by.first_name;
  const answered = set.state === "answered";
  const live = set.due_at && !answered ? countdown(set.due_at, now) : null;
  const href = answerHref(ideaId);
  const n = set.count;
  const titleId = `qcard-${variant}-${set.id}`;
  const pill = answered ? (
    <Pill variant="ok">Answered</Pill>
  ) : live ? (
    <Pill variant={live.variant === "normal" ? "neutral" : live.variant}>{countdownLabel(live, "left")}</Pill>
  ) : null;
  const label = answerLabel(set);
  const button = label ? (
    <ButtonLink href={href} variant="primary" size="sm">
      {label}
    </ButtonLink>
  ) : null;

  if (variant === "home") {
    // Home.md "Needs you": the count, the clock, who asked about which idea, each question a way into Answer
    return (
      <article className="card qcard qcard-home" aria-labelledby={titleId}>
        <header className="qcard-h">
          <p id={titleId} className="body qcard-t">
            {plural(n, "question")} from the review desk
          </p>
          {pill}
        </header>
        <p className="meta">
          {who} from the review desk asked about &quot;{set.idea.title}&quot;
        </p>
        <ol className="qcard-links">
          {set.questions.map((q, i) => (
            <li key={q.id}>
              <Link href={href} className="qcard-q">
                <span className="label">Question {i + 1}</span> <span className="body">{q.text}</span>
              </Link>
            </li>
          ))}
        </ol>
        {button ? <footer className="qcard-f">{button}</footer> : null}
      </article>
    );
  }

  if (variant === "inbox") {
    // Inbox.md, the reader's body: the questions, numbered, then the deadline. The reader above it says what it is,
    // the idea, who asked and when with the countdown, and pins "Open the conversation" and the button to its foot
    return (
      <div className="qcard qcard-inbox">
        <ol className="qcard-qs">
          {set.questions.map((q, i) => (
            <li key={q.id}>
              <span className="qcard-qn">Question {i + 1}</span>
              <span className="qcard-qt">
                {/* Partly answered (NOT DRAWN): an answered question shows a tick beside its words */}
                {q.answer?.sent && !answered ? (
                  <span className="qcard-tick" role="img" aria-label="Answered">
                    ✓{" "}
                  </span>
                ) : null}
                {q.text}
              </span>
            </li>
          ))}
        </ol>
        {answered ? null : <p className="qcard-due">{set.deadline}.</p>}
      </div>
    );
  }

  const sent = set.sent_at ? `${dayLabel(set.sent_at, now)}, ${clockLabel(set.sent_at)}` : "";
  return (
    <article className="card qcard" aria-labelledby={titleId}>
      <header className="qcard-h">
        <Avatar initials={set.by.initials} size={32} name={set.by.name} />
        <span className="meta">
          {who} from the review desk, {sent}
        </span>
        {pill}
      </header>
      <h3 id={titleId} className="h3">
        {answered
          ? `${who}’s ${plural(n, "question")}, answered`
          : `${who} has ${plural(n, "question")} for you`}
      </h3>
      {answered && set.answered_at ? (
        <p className="meta">
          Answered on {dayLabel(set.answered_at, now)}, {clockLabel(set.answered_at)}. Your answers are below,
          each added to its part of your idea.
        </p>
      ) : null}
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
      {answered ? null : (
        <footer className="qcard-f">
          <p className="meta">{set.deadline}. One at a time, typed or spoken.</p>
          {button}
        </footer>
      )}
    </article>
  );
}
