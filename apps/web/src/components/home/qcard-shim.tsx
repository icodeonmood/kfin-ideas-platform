"use client";
/**
 * A stand-in for lane B's C-QCARD (`QuestionsCard` in `@/components/review/qcard`) until it is on main (BLD-C145).
 * Same signature as lane B's (b/1pc-screens-6 at 7a1a3ed7: `ideaId`, `set`, `variant`), and the same markup and
 * classes for `variant="home"`, so Home's "Needs you" is wired the way it will run. When lane B's screens land, the
 * one import in `app/home/home.tsx` swaps to "@/components/review/qcard" and this file goes. Never create anything
 * under components/review/ or lib/desk/.
 *
 * Home.md "Needs you": "3 questions from the review desk", the clock ("3 days left", "07:38 left"), "Meera from the
 * review desk asked about "…"", each question a link into Answer (S-R3), and "Answer the questions".
 */
import Link from "next/link";
import { useEffect, useState } from "react";

import { ButtonLink } from "@/components/ui/button";
import { Pill } from "@/components/ui/pill";
import type { SharerQuestionSetResponse } from "@/lib/contracts";
import { countdown, countdownLabel, nextTickMs } from "@/lib/desk/countdown";

type Set = NonNullable<SharerQuestionSetResponse>;

export type QuestionsCardVariant = "status" | "home" | "inbox";

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

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

export function QuestionsCard({
  ideaId,
  set,
  variant = "home",
}: {
  ideaId: string;
  set: Set;
  variant?: QuestionsCardVariant;
}) {
  void variant; // Home is the only place the stand-in is used
  const now = useMinute();
  const who = set.by.first_name;
  const answered = set.state === "answered";
  const partly = !answered && set.answered > 0;
  const live = set.due_at && !answered ? countdown(set.due_at, now) : null;
  const href = `/ideas/${encodeURIComponent(ideaId)}/answer`;
  const titleId = `qcard-home-${set.id}`;
  return (
    <article className="card qcard qcard-home" aria-labelledby={titleId}>
      <header className="qcard-h">
        <p id={titleId} className="body qcard-t">
          {plural(set.count, "question")} from the review desk
        </p>
        {answered ? (
          <Pill variant="ok">Answered</Pill>
        ) : live ? (
          <Pill variant={live.variant === "normal" ? "neutral" : live.variant}>
            {countdownLabel(live, "left")}
          </Pill>
        ) : null}
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
      {answered ? null : (
        <footer className="qcard-f">
          <ButtonLink href={href} variant="primary" size="sm">
            {partly ? "Carry on answering" : "Answer the questions"}
          </ButtonLink>
        </footer>
      )}
    </article>
  );
}
