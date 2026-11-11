"use client";

/**
 * The short summary colleagues see on match cards and the wall (DEC-026). The review desk writes or corrects it,
 * for example when the assistant's summary was left blank because the person's words did not back it (BLD-C027).
 * The same checks run on it as on any text colleagues see: the patterns, then the gatekeeper, then names and
 * client names, and it may not repeat the person's own words (BLD-C046). The change is audited without the text.
 */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

export const SUMMARY_HELP =
  "Other colleagues will see this. Write it in your own words. Don't copy the person's text or add names.";
export const SUMMARY_MAX_WORDS = 25;

const TOO_LONG = `Please keep it to ${SUMMARY_MAX_WORDS} words or fewer.`;
const ERRORS: Record<string, string> = {
  text_too_short: "Please write at least 15 characters.",
  summary_too_long: TOO_LONG,
  personal_data: "Please take out personal details first.",
  summary_not_neutral: "Please take out names and client names. Colleagues will see this.",
  summary_too_close: "Please write it in your own words. It reads too close to the person's text.",
  checks_unavailable: "We can't check that just now. Please try again in a few minutes.",
  own_idea: "You cannot act on an idea you shared or are linked to. Another reviewer will take it.",
  already_decided: "This item has already been decided.",
  assigned_to_someone_else: "This item is with someone else now, so they will write the summary.",
  awaiting_hold_confirmation: "A hold is waiting for a second reviewer. The summary can change after that.",
};

export function wordCount(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

export function SummaryForm({ id, current }: { id: string; current: string }) {
  const router = useRouter();
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [text, setText] = useState(current);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const words = wordCount(text);
  const over = words > SUMMARY_MAX_WORDS;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaved(false);
    if (over) {
      setError(TOO_LONG);
      fieldRef.current?.focus();
      return;
    }
    setBusy(true);
    setError("");
    const res = await fetch(`/api/review/items/${id}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "summary", neutral_summary: text }),
    }).catch(() => null);
    const out = (await res?.json().catch(() => null)) as { error?: string } | null;
    setBusy(false);
    if (res?.ok) {
      setSaved(true);
      statusRef.current?.focus();
      router.refresh();
      return;
    }
    setError(ERRORS[String(out?.error)] ?? "That did not go through. Please try again.");
    fieldRef.current?.focus(); // the error is read with the field (aria-describedby)
  }

  return (
    <section aria-labelledby="p-summary" className="panel">
      <h2 id="p-summary">Short summary for colleagues</h2>
      {current ? null : <p className="notice">There is no short summary yet. Please write one.</p>}
      <form onSubmit={(e) => void save(e)} noValidate>
        <div className="field">
          <label htmlFor="summary-text">Short summary</label>
          <p id="summary-help" className="hint">
            {SUMMARY_HELP}
          </p>
          <textarea
            id="summary-text"
            ref={fieldRef}
            rows={3}
            value={text}
            aria-invalid={error ? true : undefined}
            aria-describedby={`summary-help summary-count${error ? " summary-error" : ""}`}
            onChange={(e) => {
              setText(e.target.value);
              setSaved(false);
            }}
          />
          <p id="summary-count" className={over ? "field-error" : "hint"} aria-live="polite">
            {words} of {SUMMARY_MAX_WORDS} words
          </p>
          {error ? (
            <p id="summary-error" className="field-error">
              {error}
            </p>
          ) : null}
        </div>
        <button type="submit" className="button" disabled={busy}>
          Save the summary
        </button>
      </form>
      <p ref={statusRef} tabIndex={-1} role="status" aria-live="polite" className="muted">
        {saved ? "Summary saved." : ""}
      </p>
    </section>
  );
}
