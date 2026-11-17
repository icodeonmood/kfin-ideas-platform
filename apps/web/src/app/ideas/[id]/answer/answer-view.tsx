"use client";

/**
 * S-R3 Answer the review desk (L-QUESTIONS.answer). One question at a time; skip and come back; each answer saves as
 * it is typed; "Check and send" lists them all; sending needs at least one answer and the rest stay open until the
 * deadline. Words about other people use their names, never a pronoun (BLD-E008).
 */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Dock, PhoneBar } from "@/components/shell/phone";
import { Button, ButtonLink } from "@/components/ui/button";
import { Empty } from "@/components/ui/empty";
import { Field, FieldMsg } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import type { SendAnswersResponse, SharerQuestionSetResponse, SetQuestion } from "@/lib/contracts";
import { countdown, countdownLabel, nextTickMs } from "@/lib/desk/countdown";
import { clockLabel, dayLabel } from "@/lib/desk/when";

type SetView = NonNullable<SharerQuestionSetResponse>;

/** A step in the row: "Question 2", named "Question 2, not answered yet" or "Question 1, answered" (Answer board). */
function StepLabel({ n, done }: { n: number; done: boolean }) {
  return (
    <>
      {done ? <span aria-hidden="true">✓ </span> : null}
      Question {n}
      <span className="vh">{done ? ", answered" : ", not answered yet"}</span>
    </>
  );
}
type Saving = "idle" | "saving" | "saved" | "failed";

function said(at: string | null, now: Date): string {
  if (!at) return "";
  const today = dayLabel(at, now) === dayLabel(now, now);
  return today ? `today ${clockLabel(at)}` : `${dayLabel(at, now)}, ${clockLabel(at)}`;
}

export function AnswerView({ ideaId, initial }: { ideaId: string; initial: SetView | null }) {
  const [set] = useState(initial);
  const [step, setStep] = useState(0); // 0..n-1 a question, n = Check and send
  const [texts, setTexts] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      (initial?.questions ?? []).map((q) => [q.id, q.answer?.sent ? "" : (q.answer?.text ?? "")]),
    ),
  );
  const [saving, setSaving] = useState<Saving>("idle");
  const [sent, setSent] = useState<SendAnswersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const heading = useRef<HTMLHeadingElement>(null);

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

  if (!set) {
    // The same for anyone but the sharer, so it never says whether the idea exists (L-QUESTIONS.answer).
    return (
      <div className="ans">
        <PhoneBar back={{ href: "/home", label: "Home" }} title="Answer" />
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
  const reviewer = set.by.first_name;
  const live = set.due_at ? countdown(set.due_at, now) : null;
  const ready = questions.filter((q) => (texts[q.id] ?? "").trim()).length;
  const answeredCount = answeredBefore.length + ready;

  function save(q: SetQuestion, text: string) {
    setTexts((t) => ({ ...t, [q.id]: text }));
    clearTimeout(timers.current[q.id]);
    timers.current[q.id] = setTimeout(async () => {
      setSaving("saving");
      const res = await fetch(`/api/questions/${encodeURIComponent(q.id)}/answer`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      }).catch(() => null);
      if (res?.ok) setSaving("saved");
      else {
        setSaving("failed");
        const body = (await res?.json().catch(() => null)) as { error?: { message: string } } | null;
        if (body?.error?.message) setError(body.error.message);
      }
    }, 700);
  }

  async function sendAll() {
    setBusy(true);
    setError(null);
    // flush any answer still waiting to save, then send
    await Promise.all(
      questions.map(async (q) => {
        const pending = timers.current[q.id];
        if (!pending) return;
        clearTimeout(pending);
        delete timers.current[q.id];
        await fetch(`/api/questions/${encodeURIComponent(q.id)}/answer`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: texts[q.id] ?? "" }),
        });
      }),
    );
    const res = await fetch(`/api/question-sets/${encodeURIComponent(set!.id)}/send`, { method: "POST" });
    const body = (await res.json().catch(() => ({}))) as SendAnswersResponse & {
      error?: { message: string };
    };
    setBusy(false);
    if (!res.ok || body.error) return setError(body.error?.message ?? "Your answers didn’t send. Try again.");
    setSent(body);
  }

  const bar = (
    <header className="ans-bar">
      <h1 className="h2" ref={sent ? undefined : heading} tabIndex={-1}>
        Answer the review desk
      </h1>
      <p className="body">
        {reviewer} from the review desk has {set.count} question{set.count === 1 ? "" : "s"} about “
        {set.idea.title}”. Answer them one at a time. Skip any you can’t answer yet and come back before you
        send.
      </p>
      <p className="ans-due">
        {live ? (
          <Pill variant={live.variant === "normal" ? "neutral" : live.variant}>
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
        <PhoneBar back={{ href: "/home", label: "Home" }} title="Answer" />
        <header className="ans-bar">
          <h1 className="h2">Answer the review desk</h1>
          <p className="body">
            {reviewer} from the review desk had {sent.count} question{sent.count === 1 ? "" : "s"} about “
            {set.idea.title}”.{" "}
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
              const done = Boolean((texts[x.id] ?? "").trim() || x.answer?.sent);
              return (
                <li key={x.id}>
                  <button type="button" className={done ? "done" : undefined} aria-disabled="true">
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
                <p className="body">
                  {(texts[q.id] ?? "").trim() ||
                    q.answer?.text ||
                    "Not answered. It stays open until the deadline."}
                </p>
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

  return (
    <div className="ans">
      <PhoneBar back={{ href: "/home", label: "Home" }} title="Answer" />
      {bar}

      <nav className="ans-steps" aria-label="Questions">
        <ol>
          {questions.map((x, i) => (
            <li key={x.id}>
              <button
                type="button"
                aria-current={step === i ? "step" : undefined}
                className={(texts[x.id] ?? "").trim() ? "done" : undefined}
                onClick={() => setStep(i)}
              >
                <StepLabel n={i + 1} done={Boolean((texts[x.id] ?? "").trim())} />
              </button>
            </li>
          ))}
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
                <p className="body">
                  {(texts[x.id] ?? "").trim() || "Not answered. It stays open until the deadline."}
                </p>
                <Button variant="text" onClick={() => setStep(i)}>
                  Change
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
                : `Send ${ready} answer${ready === 1 ? "" : "s"} to ${reviewer}`}
            </Button>
          </Dock>
        </section>
      ) : q ? (
        <section className="panel ans-sheet" aria-labelledby={`ans-q-${q.id}`}>
          <p className="meta">
            {reviewer} from the review desk asked, {said(set.sent_at, now)}
          </p>
          <p className="meta">
            Added to <span className="chip">{q.part_name}</span>
          </p>
          <h2 id={`ans-q-${q.id}`} className="h3" ref={heading} tabIndex={-1}>
            <span className="vh">Question {step + 1}: </span>
            {q.text}
          </h2>
          {/* Seams, not built yet: files on an answer (C-FILE.row, S-R3.rules/3) and "Say your answer" through
              lane C's voice route mount beside this box. */}
          <Field
            label={`Your answer to question ${step + 1}`}
            multiline
            help="Press Enter to go on. Shift + Enter adds a new line."
          >
            {(p) => (
              <textarea
                {...p}
                rows={5}
                maxLength={2000}
                value={texts[q.id] ?? ""}
                onChange={(e) => save(q, e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    setStep(step + 1);
                  }
                }}
              />
            )}
          </Field>
          {saving === "failed" && error ? (
            <FieldMsg kind="error">
              <span role="alert">{error}</span>
            </FieldMsg>
          ) : null}
          <Dock label="Move between questions">
            <Button variant="text" disabled={step === 0} onClick={() => setStep(step - 1)}>
              Back
            </Button>
            <Button variant="primary" onClick={() => setStep(step + 1)}>
              {(texts[q.id] ?? "").trim() ? "Next" : "Skip for now"}
            </Button>
          </Dock>
        </section>
      ) : null}
    </div>
  );
}
