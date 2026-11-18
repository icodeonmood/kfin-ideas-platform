"use client";
/**
 * Flag S1 "Interview" on Tell it (P-DECISIONS.experiments, L-DRAFT.parts/10; BLD-C172): after the first telling, up
 * to three short questions, one at a time, each skippable, then the draft. Copy word for word from the boards: the
 * intro and its list (Compose.md, `simulatorS1=Interview`) and the phone's question card (PhoneCompose.md, same
 * state). Lines the boards do not draw are made from a drawn one ("Question 2 of 3", the "So far we …" forms) or kept
 * for HR ("Show my draft"); docs/hr-wording/lane-c.md lists them.
 *
 * The card is a group named by its question, and its answer box is named by the question too; Enter or "Next question" sends
 * the answer (an empty box counts as a skip), "Skip this one" skips. Moving on from a question puts focus in the
 * next one's box, so the keyboard never drops to the page.
 */
import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { FieldMsg } from "@/components/ui/field";
import { hasValue, type Live } from "@/lib/compose/live";
import { kindNoun } from "@/lib/compose/hidden";
import { INTERVIEW_QUESTIONS, type InterviewQuestion } from "@/lib/flags";

export const INTERVIEW_COPY = {
  intro: "Tell it in your words first. Then three short questions, each one skippable.",
  introList: ["How often does it happen?", "Who feels it most?", "Any rough size?"],
  /** The phone's peek while the questions wait (PhoneCompose.md). */
  peek: "3 quick questions, then your draft",
  /** "Question 1 of 3. Skip any of them." as drawn; 2 and 3 follow it (for HR). */
  count: (n: number) => `Question ${n} of 3. Skip any of them.`,
  offer: (suggestion: string) => `Use “${suggestion}”`,
  next: "Next question",
  /** The last question's button: not drawn ("Done" already closes the phone's sheet beside it), kept for HR. */
  last: "Show my draft",
  skip: "Skip this one",
  /** Closes the phone's sheet (PhoneCompose.md). */
  done: "Done",
} as const;

/** Each question, in order, as drawn: the phone's first (PhoneCompose.md), the intro's list for the others
 * (Compose.md). "Who feels it most?" is a text answer here (BLD-C172): every answer goes into the draft as the
 * person's own words. */
export const QUESTIONS: Record<InterviewQuestion, { question: string; example: string | null }> = {
  often: { question: "How often does it happen, roughly?", example: "For example, about 20 times a week" },
  who: { question: "Who feels it most?", example: null },
  size: { question: "Any rough size?", example: "For example, 70 to 150" },
};

/** The phone sheet's line on what the draft found so far (PhoneCompose.md: "So far we hid 3 personal details,
 * suggested 3 sortings and found 2 similar ideas."). A part with nothing is left out, a single one is said in the
 * singular, and with nothing found there is no line (for HR). */
export function soFarLine(live: Live): string {
  const bits: string[] = [];
  const hidden = live.hidden.filter((d) => d.state === "hidden");
  if (hidden.length > 1) bits.push(`hid ${hidden.length} personal details`);
  else if (hidden[0]) bits.push(`hid 1 ${kindNoun(hidden[0].kind)}`);
  const sorts = (["who", "value", "area"] as const).filter((k) => hasValue(live.parts[k])).length;
  if (sorts) bits.push(`suggested ${sorts} ${sorts === 1 ? "sorting" : "sortings"}`);
  const similar = Array.isArray(live.parts.similar.value) ? live.parts.similar.value.length : 0;
  if (similar) bits.push(`found ${similar} similar ${similar === 1 ? "idea" : "ideas"}`);
  if (!bits.length) return "";
  const last = bits.pop()!;
  return `So far we ${bits.length ? `${bits.join(", ")} and ${last}` : last}.`;
}

/** The intro before the first telling: what will be asked (Compose.md, `simulatorS1=Interview`). */
export function InterviewIntro() {
  return (
    <div className="ivi">
      <p className="ivi-t">{INTERVIEW_COPY.intro}</p>
      <ol>
        {INTERVIEW_COPY.introList.map((q) => (
          <li key={q}>{q}</li>
        ))}
      </ol>
    </div>
  );
}

export type InterviewCardProps = {
  question: InterviewQuestion;
  /** "How often" from the person's own words, offered as "Use “…”" (the first question only, as drawn). */
  suggestion?: string | null;
  busy?: boolean;
  error?: string | null;
  /** 2 in the conversation, 3 in the phone's sheet under "Your draft". */
  headingLevel?: 2 | 3;
  /** Put focus in the answer box when this card appears (after the person moved on from the one before). */
  focusOnShow?: boolean;
  onAnswer(text: string): void;
  onSkip(): void;
};

export function InterviewCard({
  question,
  suggestion,
  busy = false,
  error,
  headingLevel = 2,
  focusOnShow = false,
  onAnswer,
  onSkip,
}: InterviewCardProps) {
  const id = useId();
  const [text, setText] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const n = INTERVIEW_QUESTIONS.indexOf(question) + 1;
  const last = n === INTERVIEW_QUESTIONS.length;
  const q = QUESTIONS[question];
  const H = headingLevel === 3 ? "h3" : "h2";
  const offer = suggestion && question === "often" && text.trim() !== suggestion ? suggestion : null;

  useEffect(() => {
    if (focusOnShow) input.current?.focus();
  }, [focusOnShow]);

  const next = () => {
    if (busy) return;
    const words = text.trim();
    if (words) onAnswer(words);
    else onSkip(); // nothing typed: the question is skipped, as "Skip this one"
  };

  return (
    <div className="iv" role="group" aria-labelledby={`${id}-q`}>
      <div className="ivd" aria-hidden="true">
        {INTERVIEW_QUESTIONS.map((k, i) => (
          <span key={k} className={i < n - 1 ? "d" : i === n - 1 ? "n" : ""} />
        ))}
      </div>
      <p className="ivc">{INTERVIEW_COPY.count(n)}</p>
      <H id={`${id}-q`} className="ivq">
        {q.question}
      </H>
      {offer ? (
        <div className="ivs">
          <button
            type="button"
            className="chip"
            onClick={() => {
              setText(offer);
              input.current?.focus();
            }}
          >
            {INTERVIEW_COPY.offer(offer)}
          </button>
        </div>
      ) : null}
      <input
        ref={input}
        id={`${id}-a`}
        className="fld"
        type="text"
        value={text}
        placeholder={q.example ?? undefined}
        maxLength={5000}
        enterKeyHint="next"
        aria-labelledby={`${id}-q`}
        aria-describedby={error ? `${id}-e` : undefined}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key !== "Enter" || e.nativeEvent.isComposing) return;
          e.preventDefault();
          next();
        }}
      />
      {error ? <FieldMsg id={`${id}-e`}>{error}</FieldMsg> : null}
      <div className="ivb">
        <Button variant="soft" size="sm" busy={busy} onClick={next}>
          {last ? INTERVIEW_COPY.last : INTERVIEW_COPY.next}
        </Button>
        <button
          type="button"
          className="tb"
          aria-disabled={busy || undefined}
          onClick={() => {
            if (!busy) onSkip();
          }}
        >
          {INTERVIEW_COPY.skip}
        </button>
      </div>
    </div>
  );
}
