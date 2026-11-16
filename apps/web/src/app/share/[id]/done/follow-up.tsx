"use client";

/** After review: answer the desk's question (it pauses their clock). "Disagree with this?" is retired (DEC-106). */
import { useState } from "react";

export function FollowUp({
  id,
  question,
  onChanged,
  headingLevel = 4,
}: {
  id: string;
  question: { text: string; due: string } | null;
  onChanged: () => Promise<void>;
  headingLevel?: 3 | 4;
}) {
  const QuestionHeading = headingLevel === 3 ? "h3" : "h4";
  const [answer, setAnswer] = useState("");
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  async function post(text: string, done: string) {
    setBusy(true);
    const res = await fetch(`/api/ideas/${id}/answer`, {
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
            void post(answer, "Thanks. Your answer is with the review desk.");
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
    </div>
  );
}
