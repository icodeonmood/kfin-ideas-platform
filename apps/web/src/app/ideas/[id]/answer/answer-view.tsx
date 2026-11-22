"use client";

/**
 * S-R3 Answer the review desk (L-QUESTIONS.answer). One question at a time; skip and come back; each answer saves as
 * it is typed; "Check and send" lists them all; sending needs at least one answer and the rest stay open until the
 * deadline. Words about other people use their names, never a pronoun (BLD-E008). The reviewer is never named: the
 * sharer reads "the review desk" wherever the board names the person who asked (DEC-111).
 *
 * The "+" under each answer box (BLD-B275; DEC-124, C-PROMPT.anatomy/2; named as the Answer board names it, "Attach
 * files to this answer") adds files to that answer: each is one of the
 * idea's own files (BLD-B274), checked as DEC-107 says, and an answer with a file and no words counts as answered, as
 * the worker counts it. Files only: no folder or link on S-R3 yet.
 */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Dock, PhoneBar } from "@/components/shell/phone";
import { AttachButton } from "@/components/ui/attach-button";
import { Button, ButtonLink } from "@/components/ui/button";
import { Empty } from "@/components/ui/empty";
import { Field, FieldMsg } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import type { SendAnswersResponse, SharerQuestionSetResponse, SetQuestion } from "@/lib/contracts";
import {
  ANSWER_FILES_COPY,
  attachedOf,
  counts,
  filesLine,
  isAnswered,
  seedRows,
  sentFiles,
} from "@/lib/desk/answer-files";
import { countdown, countdownLabel, nextTickMs } from "@/lib/desk/countdown";
import {
  MAX_ANSWER,
  NEAR_LIMIT,
  putAnswer,
  RETRY_MS,
  SAVE_AFTER_MS,
  tellInboxCounts,
  type SaveResult,
} from "@/lib/desk/answers";
import { call } from "@/lib/desk/reply";
import { clockLabel, dayLabel } from "@/lib/desk/when";
import { REVIEW_DESK, REVIEW_DESK_START } from "@/lib/review-desk";

import { AnswerFileRows, useAnswerFiles, type AnswerTarget } from "./answer-files";

type SetView = NonNullable<SharerQuestionSetResponse>;

/** "Home" back: the compact bar on a phone (S-R3.rules/5), a back link above the review bar on desktop (Answer board).
 * Its one chevron and 44px height are the shared `.back` (lane D, BLD-B261). */
function Back() {
  return (
    <>
      <PhoneBar back={{ href: "/", label: "Home" }} title="Answer" />
      <Link href="/" className="back ans-back">
        Home
      </Link>
    </>
  );
}

/** A step in the row: "Question 2", named "Question 2, not answered yet" or "Question 1, answered" (Answer board).
 * The name is the button's aria-label: a hidden span is laid out as a block, so a name built from it reads
 * "Question 1 , answered", with a stray space before the comma. The label starts with the words on the button
 * (WCAG 2.5.3). */
function stepName(n: number, done: boolean): string {
  return `Question ${n}, ${done ? "answered" : "not answered yet"}`;
}

function StepLabel({ n, done }: { n: number; done: boolean }) {
  return (
    <>
      {done ? <span aria-hidden="true">✓ </span> : null}
      Question {n}
    </>
  );
}
type Saving = "idle" | "saving" | "saved" | "failed";

function said(at: string | null, now: Date): string {
  if (!at) return "";
  const today = dayLabel(at, now) === dayLabel(now, now);
  return today ? `today ${clockLabel(at)}` : `${dayLabel(at, now)}, ${clockLabel(at)}`;
}

/** An answer's words, then the line for its files ("Two screenshots attached, folio hidden.", Answer.md), or the
 * board's line for a question not answered. */
function AnswerLines({ words, files }: { words: string; files: string }) {
  if (!words && !files) return <p className="body">Not answered. It stays open until the deadline.</p>;
  return (
    <>
      {words ? <p className="body">{words}</p> : null}
      {files ? <p className="body">{files}</p> : null}
    </>
  );
}

export function AnswerView({
  ideaId,
  initial,
  blackout = false,
}: {
  ideaId: string;
  initial: SetView | null;
  /** `files.blackout` (DEC-107): "Hide it for me" on a file is offered only while it is on, as on Check it. */
  blackout?: boolean;
}) {
  const [set] = useState(initial);
  const [step, setStep] = useState(0); // 0..n-1 a question, n = Check and send
  const [texts, setTexts] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      (initial?.questions ?? []).map((q) => [q.id, q.answer?.sent ? "" : (q.answer?.text ?? "")]),
    ),
  );
  // What the server holds for each answer, from its own reply: the Sent list reads only these (B3)
  const [stored, setStored] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      (initial?.questions ?? []).flatMap((q) =>
        q.answer && !q.answer.sent ? [[q.id, q.answer.text] as const] : [],
      ),
    ),
  );
  const latest = useRef(texts);
  const [saving, setSaving] = useState<Saving>("idle");
  const [sent, setSent] = useState<SendAnswersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const heading = useRef<HTMLHeadingElement>(null);
  // Each unsent answer's row id, once the server has one: a file goes to it (BLD-B275)
  const answerIds = useRef<Record<string, string>>(
    Object.fromEntries(
      (initial?.questions ?? []).flatMap((q) =>
        q.answer && !q.answer.sent ? [[q.id, q.answer.id] as const] : [],
      ),
    ),
  );
  // Each question's save while it is on its way, from the autosave or for a file, so a file waits for it (BLD-B275)
  const saving$ = useRef<Record<string, Promise<SaveResult>>>({});
  // The one save that makes an answer's row, while it is on its way, so two quick picks never make two
  const creating = useRef<Record<string, Promise<AnswerTarget>>>({});

  /** One PUT of an answer, registered for its question while it is on its way. */
  function put(id: string, text: string): Promise<SaveResult> {
    const p = putAnswer(id, text);
    saving$.current[id] = p;
    void p.then(() => {
      if (saving$.current[id] === p) delete saving$.current[id];
    });
    return p;
  }

  /** What a save's reply means on screen. A failed save shows the failure line and is tried again after a pause,
   * unless the person has typed since (that typing saves it). With `quiet`, the worker's refusal is left to the file
   * row that asked for the save, so it shows once. */
  function saved(id: string, text: string, r: SaveResult, quiet = false): void {
    if (r.ok) {
      if (r.id) answerIds.current[id] = r.id;
      setStored((m) => ({ ...m, [id]: r.text }));
      setSaving("saved");
      setError(null);
      return;
    }
    if (quiet && !r.retry) {
      setSaving("idle");
      return;
    }
    setSaving("failed");
    setError(r.message);
    if (r.retry) {
      timers.current[id] = setTimeout(() => {
        delete timers.current[id];
        if (latest.current[id] === text) void store(id, text);
      }, RETRY_MS);
    }
  }

  /** Saves one answer now; the reply's text is what the server holds. */
  async function store(id: string, text: string): Promise<boolean> {
    setSaving("saving");
    const r = await put(id, text);
    saved(id, text, r);
    return r.ok;
  }

  /** Where a file for this question goes (BLD-B275): the answer's row id, after any save already on its way; when
   * there is still none, the answer is saved as it stands (an empty answer saves too, and makes the row). One save
   * per question at a time. A refusal from the worker (the set closed, the answer sent or held by a co-sharer) comes
   * back as its words, for the row; a failure that may pass is null (the box's line shows, as for typing). */
  async function answerIdOf(qid: string): Promise<AnswerTarget> {
    const have = answerIds.current[qid];
    if (have) return { id: have };
    const making = creating.current[qid];
    if (making) return making;
    const made = (async (): Promise<AnswerTarget> => {
      const onWay = saving$.current[qid];
      if (onWay) {
        await onWay;
        const id = answerIds.current[qid];
        if (id) return { id };
      }
      clearTimeout(timers.current[qid]); // this save takes the words as they stand
      delete timers.current[qid];
      const text = latest.current[qid] ?? "";
      setSaving("saving");
      const r = await put(qid, text);
      saved(qid, text, r, true);
      if (r.ok) return r.id ? { id: r.id } : null;
      return r.retry ? null : { refused: r.message };
    })();
    creating.current[qid] = made;
    try {
      return await made;
    } finally {
      delete creating.current[qid];
    }
  }

  const [seed] = useState(() => seedRows(initial?.questions ?? []));
  const files = useAnswerFiles(seed, answerIdOf);
  const plus = useRef<HTMLButtonElement>(null);
  const chooser = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    const tick = () => {
      setNow(new Date());
      t = setTimeout(tick, nextTickMs());
    };
    t = setTimeout(tick, nextTickMs());
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    heading.current?.focus();
  }, [step, sent]);

  // Saves and retries still waiting stop when the screen goes
  useEffect(() => {
    const pending = timers.current;
    return () => Object.values(pending).forEach(clearTimeout);
  }, []);

  if (!set) {
    // The same for anyone but the sharer, so it never says whether the idea exists (L-QUESTIONS.answer).
    return (
      <div className="ans">
        <Back />
        <h1 className="h2">Answer the review desk</h1>
        <Empty
          title="Nothing to answer right now"
          align="left"
          level={2}
          action={
            <ButtonLink variant="line" href={`/ideas/${encodeURIComponent(ideaId)}`}>
              See your idea
            </ButtonLink>
          }
        >
          When the review desk asks you something about this idea, the questions show here.
        </Empty>
      </div>
    );
  }

  const questions = set.questions.filter((q) => !q.answer?.sent);
  const answeredBefore = set.questions.filter((q) => q.answer?.sent);
  const n = questions.length;
  const live = set.due_at ? countdown(set.due_at, now) : null;
  const ready = questions.filter((q) => isAnswered(texts[q.id], files.rows[q.id])).length;
  const answeredCount = answeredBefore.length + ready;

  function save(q: SetQuestion, text: string) {
    latest.current = { ...latest.current, [q.id]: text };
    setTexts((t) => ({ ...t, [q.id]: text }));
    clearTimeout(timers.current[q.id]);
    timers.current[q.id] = setTimeout(() => {
      delete timers.current[q.id]; // fired: gone, so a send never flushes it twice
      void store(q.id, text);
    }, SAVE_AFTER_MS);
  }

  async function sendAll() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      // Files still on their way go first (lane F's rule for S-08's box), then the words
      await files.settle();
      // Flush every answer the server does not hold yet (still waiting, or failed), and stop if any fails
      const flushes = questions
        .filter((q) => timers.current[q.id] !== undefined || (texts[q.id] ?? "") !== (stored[q.id] ?? ""))
        .map((q) => {
          clearTimeout(timers.current[q.id]);
          delete timers.current[q.id];
          return store(q.id, texts[q.id] ?? "");
        });
      if (!(await Promise.all(flushes)).every(Boolean)) return;
      const r = await call<SendAnswersResponse>(`/api/question-sets/${encodeURIComponent(set!.id)}/send`, {
        method: "POST",
      });
      if (!r.ok) {
        setError(r.status === 0 ? "Your answers didn’t send. Try again." : r.error.message);
        return;
      }
      setSent(r.body);
      void tellInboxCounts(); // the item left Needs you: every Inbox count is sent again (L-INBOX.rules/1, /3)
    } finally {
      setBusy(false);
    }
  }

  const bar = (
    <header className="ans-bar">
      <h1 className="h2" ref={sent ? undefined : heading} tabIndex={-1}>
        Answer the review desk
      </h1>
      <p className="body">
        {REVIEW_DESK_START} has {set.count} question{set.count === 1 ? "" : "s"} about &quot;
        {set.idea.title}&quot;. Answer them one at a time. Skip any you can’t answer yet and come back before
        you send.
      </p>
      <p className="ans-due">
        {live ? (
          <Pill variant={live.variant === "normal" ? "neutral" : live.variant} countdown>
            {countdownLabel(live, "left to answer")}
          </Pill>
        ) : null}
        <span className="meta">{set.deadline}</span>
      </p>
    </header>
  );

  if (sent) {
    const all = sent.answered === sent.count;
    return (
      <div className="ans">
        <Back />
        <header className="ans-bar">
          <h1 className="h2">Answer the review desk</h1>
          <p className="body">
            {REVIEW_DESK_START} had {sent.count} question{sent.count === 1 ? "" : "s"} about &quot;
            {set.idea.title}&quot;.{" "}
            {all ? `You answered all ${sent.count}.` : `You answered ${sent.answered} of ${sent.count}.`}
          </p>
          <p className="ans-due">
            <span className="meta">{sent.spare}</span>
            {sent.decides_by ? <span className="meta">{sent.decides_by}</span> : null}
          </p>
        </header>
        <nav className="ans-steps" aria-label="Questions">
          <ol>
            {set.questions.map((x, i) => {
              const done = Boolean(
                (stored[x.id] ?? "").trim() || x.answer?.sent || (files.rows[x.id] ?? []).some(counts),
              );
              return (
                <li key={x.id}>
                  <button
                    type="button"
                    className={done ? "done" : undefined}
                    aria-disabled="true"
                    aria-label={stepName(i + 1, done)}
                  >
                    <StepLabel n={i + 1} done={done} />
                  </button>
                </li>
              );
            })}
            <li>
              <button type="button" aria-current="step" aria-disabled="true">
                Sent
              </button>
            </li>
          </ol>
          <p className="meta">{sent.progress}</p>
        </nav>
        <section className="panel ans-sent" aria-labelledby="ans-sent-t">
          <div role="status" className="ans-sent-h">
            <p className="meta">{sent.sent_line}</p>
            <h2 id="ans-sent-t" className="h3" ref={heading} tabIndex={-1}>
              Your answers are with the review desk
            </h2>
            <p className="body">
              Each answer is added to its part of your idea and posted in your conversation with the review
              desk.{" "}
              {sent.decides_by
                ? `${sent.decides_by}, and the decision comes to your Inbox.`
                : "The decision comes to your Inbox."}
            </p>
          </div>
          <ol className="ans-list">
            {set.questions.map((q) => (
              <li key={q.id}>
                <p className="body">{q.text}</p>
                <p className="meta">Added to {q.part_name}</p>
                <AnswerLines
                  words={(q.answer?.sent ? q.answer.text : (stored[q.id] ?? "")).trim()}
                  files={filesLine(q.answer?.sent ? sentFiles(q.answer.files) : attachedOf(files.rows[q.id]))}
                />
              </li>
            ))}
          </ol>
          <div className="ans-links">
            <Link href={`/ideas/${encodeURIComponent(ideaId)}/conversation`}>See the conversation</Link>
            <Link href={`/ideas/${encodeURIComponent(ideaId)}`}>See your idea</Link>
          </div>
        </section>
      </div>
    );
  }

  const checking = step >= n;
  const q = questions[step];
  const length = q ? (texts[q.id] ?? "").trim().length : 0;

  return (
    <div className="ans">
      <Back />
      {bar}

      <nav className="ans-steps" aria-label="Questions">
        <ol>
          {questions.map((x, i) => {
            const done = isAnswered(texts[x.id], files.rows[x.id]);
            return (
              <li key={x.id}>
                <button
                  type="button"
                  aria-current={step === i ? "step" : undefined}
                  className={done ? "done" : undefined}
                  aria-label={stepName(i + 1, done)}
                  onClick={() => setStep(i)}
                >
                  <StepLabel n={i + 1} done={done} />
                </button>
              </li>
            );
          })}
          <li>
            {/* The board names it "Check your answers and send" and shows "Check and send". */}
            <button type="button" aria-current={checking ? "step" : undefined} onClick={() => setStep(n)}>
              Check <span className="vh">your answers </span>and send
            </button>
          </li>
        </ol>
        <p className="meta" aria-live="polite">
          {answeredCount} of {set.count} answered
          {saving === "saving" ? " · Saving…" : saving === "saved" ? " · Saved" : ""}
        </p>
      </nav>

      {checking ? (
        <section className="panel ans-sheet" aria-labelledby="ans-check-t">
          <h2 id="ans-check-t" className="h3" ref={heading} tabIndex={-1}>
            Check your answers
          </h2>
          <ol className="ans-list">
            {questions.map((x, i) => (
              <li key={x.id}>
                <p className="body">{x.text}</p>
                <p className="meta">Added to {x.part_name}</p>
                <AnswerLines
                  words={(texts[x.id] ?? "").trim()}
                  files={filesLine(attachedOf(files.rows[x.id]))}
                />
                <Button variant="text" onClick={() => setStep(i)}>
                  Change<span className="vh"> your answer to question {i + 1}</span>
                </Button>
              </li>
            ))}
          </ol>
          {error ? (
            <FieldMsg kind="error">
              <span role="alert">{error}</span>
            </FieldMsg>
          ) : null}
          <Dock label="Send your answers">
            <Button
              variant="primary"
              disabled={ready === 0}
              busy={busy}
              busyLabel="Sending…"
              onClick={() => void sendAll()}
            >
              {ready === 0
                ? "Answer at least one question"
                : `Send ${ready} answer${ready === 1 ? "" : "s"} to ${REVIEW_DESK}`}
            </Button>
          </Dock>
        </section>
      ) : q ? (
        <section className="panel ans-sheet" aria-labelledby={`ans-q-${q.id}`}>
          <p className="meta">
            {REVIEW_DESK_START} asked, {said(set.sent_at, now)}
          </p>
          <p className="meta">
            Added to <span className="chip">{q.part_name}</span>
          </p>
          <h2 id={`ans-q-${q.id}`} className="h3" ref={heading} tabIndex={-1}>
            <span className="vh">Question {step + 1}: </span>
            {/* The question in its own element, as the board draws it apart from its number (J-TRACK/4) */}
            <span>{q.text}</span>
          </h2>
          <Field
            label={`Your answer to question ${step + 1}`}
            multiline
            help={
              <>
                <span className="help-l">Press Enter to go on. Shift + Enter adds a new line.</span>
                {length >= NEAR_LIMIT ? (
                  <span className="help-l" aria-live="polite">
                    {length.toLocaleString("en-IN")} of {MAX_ANSWER.toLocaleString("en-IN")} characters
                  </span>
                ) : null}
              </>
            }
          >
            {(p) => (
              <textarea
                {...p}
                rows={5}
                maxLength={MAX_ANSWER}
                value={texts[q.id] ?? ""}
                onChange={(e) => save(q, e.target.value)}
                onKeyDown={(e) => {
                  // An IME's Enter picks a word; it never moves on
                  if (e.nativeEvent.isComposing || e.keyCode === 229) return;
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    setStep(step + 1);
                  }
                }}
              />
            )}
          </Field>
          {/* The box's tool row (C-PROMPT.anatomy/2, DEC-124): the "+", with the Answer board's name and tooltip, opens
              the system's file chooser; focus stays on it after picking. Its rows follow, under the box (C-FILE.row). */}
          <div className="ans-tools">
            <AttachButton
              ref={plus}
              label={ANSWER_FILES_COPY.attach}
              tooltip={ANSWER_FILES_COPY.attachTip}
              onClick={() => {
                files.loadConfig();
                chooser.current?.click();
              }}
            />
            <input
              ref={chooser}
              type="file"
              multiple
              hidden
              tabIndex={-1}
              onChange={(e) => {
                const chosen = Array.from(e.target.files ?? []);
                e.target.value = "";
                if (chosen.length) files.addFiles(q.id, chosen);
                requestAnimationFrame(() => plus.current?.focus());
              }}
            />
          </div>
          <AnswerFileRows
            rows={files.rows[q.id] ?? []}
            limitMb={files.limitMb}
            canHide={blackout}
            onRetry={(key) => void files.retry(q.id, key)}
            onHide={(key) => void files.hide(q.id, key)}
            onRemove={(key) =>
              void files.remove(q.id, key).then(() => requestAnimationFrame(() => plus.current?.focus()))
            }
          />
          {error ? (
            <FieldMsg kind="error">
              <span role="alert">{error}</span>
            </FieldMsg>
          ) : null}
          <Dock label="Move between questions">
            <Button variant="text" disabled={step === 0} onClick={() => setStep(step - 1)}>
              Back
            </Button>
            <Button variant="primary" onClick={() => setStep(step + 1)}>
              {isAnswered(texts[q.id], files.rows[q.id]) ? "Next" : "Skip for now"}
            </Button>
          </Dock>
        </section>
      ) : null}
    </div>
  );
}
