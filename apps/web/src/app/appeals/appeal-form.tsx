"use client";

/** File an appeal (§4.12): grounds, a statement of up to 500 words, links (stored, never opened by the platform)
 * and, if wanted, a request for a 10-minute hearing. */
import { useRouter } from "next/navigation";
import { useId, useRef, useState } from "react";

const GROUNDS: [string, string][] = [
  ["process_not_followed", "The process was not followed"],
  ["misunderstood_or_wrongly_merged", "It was misunderstood, or grouped with ideas it does not belong with"],
  ["new_evidence", "There is new evidence"],
];
const ERRORS: Record<string, string> = {
  grounds_required: "Please choose at least one reason.",
  statement_too_long: "Please keep the statement to 500 words.",
  statement_too_short: "Please say a little more (at least 30 characters).",
  personal_data:
    "Please take out personal details, such as an investor's or customer's name, PAN or phone number.",
  links_at_most_5: "Please give at most five links.",
  links_must_be_web_addresses: "Links must be web addresses that start with https://.",
  already_appealed: "This decision has already been appealed.",
  window_closed: "The time to appeal this decision has passed.",
  not_appealable: "This decision can't be appealed.",
  checks_unavailable: "We couldn't check your statement just now. Please try again in a few minutes.",
  no_panel_available:
    "There is no committee member free of a link to this group. Please contact the 1% Club team.",
};

export function AppealForm({ decisionId, closes }: { decisionId: string; closes: string }) {
  const router = useRouter();
  const id = useId();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [grounds, setGrounds] = useState<string[]>([]);
  const [statement, setStatement] = useState("");
  const [links, setLinks] = useState("");
  const [hearing, setHearing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const words = statement.trim() ? statement.trim().split(/\s+/).length : 0;

  async function submit() {
    setBusy(true);
    setMessage(null);
    const res = await fetch("/api/appeals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        decision_id: decisionId,
        grounds,
        statement,
        hearing,
        links: links
          .split("\n")
          .map((l) => l.trim())
          .filter(Boolean),
      }),
    }).catch(() => null);
    const out = (await res?.json().catch(() => null)) as {
      error?: string;
      banner?: string;
      appeal_id?: string;
    } | null;
    setBusy(false);
    setMessage(
      res?.ok
        ? {
            text: `Your appeal ${out?.appeal_id} is with the panel. You will hear within 15 working days.`,
            error: false,
          }
        : {
            text: out?.banner ?? ERRORS[String(out?.error)] ?? "That did not go through. Please try again.",
            error: true,
          },
    );
    statusRef.current?.focus();
    if (res?.ok) router.refresh();
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <p
        ref={statusRef}
        tabIndex={-1}
        role="status"
        aria-live="polite"
        className={message?.error ? "field-error" : "muted"}
      >
        {message?.text ?? ""}
      </p>
      <p>You can appeal until {closes}.</p>
      <fieldset>
        <legend>Why you are appealing</legend>
        {GROUNDS.map(([v, l]) => (
          <label key={v}>
            <input
              type="checkbox"
              checked={grounds.includes(v)}
              onChange={(e) =>
                setGrounds(e.target.checked ? [...grounds, v] : grounds.filter((g) => g !== v))
              }
            />{" "}
            {l}
          </label>
        ))}
      </fieldset>
      <div className="field">
        <label htmlFor={`${id}-statement`}>Your statement (up to 500 words)</label>
        <textarea
          id={`${id}-statement`}
          rows={6}
          maxLength={4000}
          aria-describedby={`${id}-count`}
          value={statement}
          onChange={(e) => setStatement(e.target.value)}
        />
        <p id={`${id}-count`} className="muted">
          {words} of 500 words. Leave out personal details of investors, customers or colleagues.
        </p>
      </div>
      <div className="field">
        <label htmlFor={`${id}-links`}>
          Links to evidence, one per line (up to five; the committee opens them, the platform never does)
        </label>
        <textarea id={`${id}-links`} rows={2} value={links} onChange={(e) => setLinks(e.target.value)} />
      </div>
      <label>
        <input type="checkbox" checked={hearing} onChange={(e) => setHearing(e.target.checked)} /> I would
        like a 10-minute hearing with the panel
      </label>
      <p>
        <button type="submit" className="button" disabled={busy}>
          Send my appeal
        </button>
      </p>
    </form>
  );
}
