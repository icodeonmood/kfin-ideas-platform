"use client";

/** After review: answer the desk's question (it pauses their clock), or "Disagree with this?" (§4.12 day one). */
import { useState } from "react";

export function FollowUp({
  id,
  question,
  canDisagree,
  onChanged,
  headingLevel = 4,
}: {
  id: string;
  question: { text: string; due: string } | null;
  canDisagree: boolean;
  onChanged: () => Promise<void>;
  headingLevel?: 3 | 4;
}) {
  const QuestionHeading = headingLevel === 3 ? "h3" : "h4";
  const [answer, setAnswer] = useState("");
  const [reason, setReason] = useState("");
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  async function post(kind: "answer" | "disagree", text: string, done: string) {
    setBusy(true);
    const res = await fetch(`/api/ideas/${id}/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }).catch(() => null);
    const out = (await res?.json().catch(() => null)) as { error?: string } | null;
    setBusy(false);
    if (!res?.ok) {
      setMessage({
        text:
          out?.error === "text_too_short"
            ? "Please write a little more."
            : out?.error === "personal_data"
              ? "Please take out personal details first."
              : "That did not go through. Please try again.",
        error: true,
      });
      return;
    }
    setMessage({ text: done, error: false });
    setOpen(false);
    await onChanged();
  }

  return (
    <div>
      <p role="status" aria-live="polite" className={message?.error ? "field-error" : "muted"}>
        {message?.text ?? ""}
      </p>
      {question ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void post("answer", answer, "Thanks. Your answer is with the review desk.");
          }}
        >
          <QuestionHeading>The review desk asked</QuestionHeading>
          <p>{question.text}</p>
          <div className="field">
            <label htmlFor="fu-answer">Your answer</label>
            <textarea id="fu-answer" rows={3} value={answer} onChange={(e) => setAnswer(e.target.value)} />
          </div>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            Send my answer
          </button>
        </form>
      ) : null}
      {canDisagree ? (
        open ? (
          <form
            id="fu-disagree"
            onSubmit={(e) => {
              e.preventDefault();
              void post("disagree", reason, "Thanks. The core committee will look at it.");
            }}
          >
            <div className="field">
              <label htmlFor="fu-reason">What should the committee know? (at least 15 characters)</label>
              <textarea id="fu-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
            </div>
            <button type="submit" className="btn btn-secondary" disabled={busy}>
              Send to the core committee
            </button>
          </form>
        ) : (
          <button
            type="button"
            className="btn btn-quiet"
            aria-expanded={false}
            aria-controls="fu-disagree"
            onClick={() => setOpen(true)}
          >
            Disagree with this?
          </button>
        )
      ) : null}
    </div>
  );
}
