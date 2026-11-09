"use client";

/** The panel chair records the outcome (§4.12 step 4): the decision stands, back to scoring, or overturned, with
 * reasons the colleagues read. Nothing is pre-selected. */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

const ERRORS: Record<string, string> = {
  outcome_required: "Please choose an outcome.",
  reason_too_short: "Please give fuller reasons (at least 40 characters).",
  reason_required: "Please give the panel's reasons.",
  personal_data: "Please take out personal details, such as an investor's or customer's name or numbers.",
  panel_chair_only: "The panel's chair records the outcome.",
  already_decided: "This appeal has already been decided.",
  conflict_of_interest: "You are now linked to this group, so you can't record the outcome.",
};
const OUTCOMES: [string, string][] = [
  ["upheld", "The decision stands"],
  ["re_score", "Back to scoring, with a direction for the committee"],
  ["overturned", "Overturned"],
];

export function AppealDecision({
  id,
  open,
  chair,
  outcome,
  reasons,
}: {
  id: string;
  open: boolean;
  chair: boolean;
  outcome: string | null;
  reasons: string | null;
}) {
  const router = useRouter();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [choice, setChoice] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);

  async function submit() {
    if (!choice) {
      setMessage({ text: ERRORS.outcome_required!, error: true });
      statusRef.current?.focus();
      return;
    }
    setBusy(true);
    setMessage(null);
    const res = await fetch(`/api/appeals/${id}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ outcome: choice, reasons: text }),
    }).catch(() => null);
    const out = (await res?.json().catch(() => null)) as { error?: string; banner?: string } | null;
    setBusy(false);
    setMessage(
      res?.ok
        ? { text: "Recorded. The colleagues are told.", error: false }
        : {
            text: out?.banner ?? ERRORS[String(out?.error)] ?? "That did not go through. Please try again.",
            error: true,
          },
    );
    statusRef.current?.focus();
    if (res?.ok) router.refresh();
  }

  return (
    <section aria-labelledby="a-outcome" className="panel">
      <h2 id="a-outcome">Outcome</h2>
      <p
        ref={statusRef}
        tabIndex={-1}
        role="status"
        aria-live="polite"
        className={message?.error ? "field-error" : "muted"}
      >
        {message?.text ?? ""}
      </p>
      {!open ? (
        <>
          <p>Heard: {OUTCOMES.find(([v]) => v === outcome)?.[1] ?? outcome}.</p>
          {reasons ? <p>{reasons}</p> : null}
        </>
      ) : !chair ? (
        <p>The panel discusses the appeal; its chair records the outcome.</p>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <fieldset>
            <legend>The panel&apos;s decision</legend>
            {OUTCOMES.map(([v, l]) => (
              <label key={v}>
                <input type="radio" name="a-out" checked={choice === v} onChange={() => setChoice(v)} /> {l}
              </label>
            ))}
          </fieldset>
          <div className="field">
            <label htmlFor="a-reasons">Reasons (the colleagues read these; at least 40 characters)</label>
            <textarea
              id="a-reasons"
              rows={5}
              maxLength={1000}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </div>
          <button type="submit" className="button" disabled={busy}>
            Record the outcome
          </button>
        </form>
      )}
    </section>
  );
}
