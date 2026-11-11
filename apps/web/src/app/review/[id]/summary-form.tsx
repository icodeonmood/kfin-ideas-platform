"use client";

/**
 * The short summary colleagues see on match cards and the wall (DEC-026). The review desk writes or corrects it,
 * for example when the assistant's summary was left blank because the person's words did not back it (BLD-C027).
 * The same checks run on it as on any text colleagues see: the patterns, then the gatekeeper, then names and
 * client names. The change is audited without the text.
 */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

export const SUMMARY_HELP =
  "Other colleagues will see this. Write it in your own words. Don't copy the person's text or add names.";

const ERRORS: Record<string, string> = {
  text_too_short: "Please write at least 15 characters.",
  summary_too_long: "Please keep it to 25 words or fewer.",
  personal_data: "Please take out personal details first.",
  summary_not_neutral: "Please take out names and client names. Colleagues will see this.",
  checks_unavailable: "We can't check that just now. Please try again in a few minutes.",
  own_idea: "You cannot act on an idea you shared or are linked to. Another reviewer will take it.",
};

export function SummaryForm({ id, current }: { id: string; current: string }) {
  const router = useRouter();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [text, setText] = useState(current);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    const res = await fetch(`/api/review/items/${id}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "summary", neutral_summary: text }),
    }).catch(() => null);
    const out = (await res?.json().catch(() => null)) as { error?: string } | null;
    setBusy(false);
    setMessage(
      res?.ok
        ? { text: "Summary saved.", error: false }
        : { text: ERRORS[String(out?.error)] ?? "That did not go through. Please try again.", error: true },
    );
    statusRef.current?.focus();
    if (res?.ok) router.refresh();
  }

  return (
    <section aria-labelledby="p-summary" className="panel">
      <h2 id="p-summary">Short summary for colleagues</h2>
      {current ? null : <p className="notice">There is no short summary yet. Please write one.</p>}
      <form onSubmit={(e) => void save(e)}>
        <div className="field">
          <label htmlFor="summary-text">Short summary</label>
          <p id="summary-help" className="hint">
            {SUMMARY_HELP}
          </p>
          <textarea
            id="summary-text"
            rows={3}
            maxLength={220}
            value={text}
            aria-describedby="summary-help"
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <button type="submit" className="button" disabled={busy}>
          Save the summary
        </button>
      </form>
      <p
        ref={statusRef}
        tabIndex={-1}
        role="status"
        aria-live="polite"
        className={message?.error ? "field-error" : "muted"}
      >
        {message?.text ?? ""}
      </p>
    </section>
  );
}
