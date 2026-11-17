"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

// No board draws this form (BLD-E042 keeps /ones/write/:id); every line below waits for HR's sign-off
const ERRORS: Record<string, string> = {
  // NOT DRAWN (BLD-E044): HR sign-off
  personal_data: "Please take out any personal details (numbers, addresses, investor names).",
  // NOT DRAWN (BLD-E044): HR sign-off
  text_needs_review: "Please reword this: it reads as off-topic or unkind, so we can't save it as it is.",
  // NOT DRAWN (BLD-E044): HR sign-off
  names_not_allowed: "Leave out the names of colleagues and clients: everyone will see this.",
  // NOT DRAWN (BLD-E044): HR sign-off
  text_too_short: "Please write at least a short sentence.",
  // NOT DRAWN (BLD-E044): HR sign-off
  text_too_long: "Please keep it under 600 characters.",
  // NOT DRAWN (BLD-E044): HR sign-off
  already_written: "You've already written a message for this.",
  // NOT DRAWN (BLD-E044): HR sign-off
  checks_unavailable: "We can't check text just now. Please try again in a few minutes.",
};
// NOT DRAWN (BLD-E044): HR sign-off
const NOT_SAVED = "That didn't save. Please try again.";
// NOT DRAWN (BLD-E044): HR sign-off
const LABEL = "Your message";
// NOT DRAWN (BLD-E044): HR sign-off
const HINT = "A few sentences. What did they do that mattered? No personal details.";
// NOT DRAWN (BLD-E044): HR sign-off
const SEND = "Send your message";

export function WriteForm({ proposalId, as }: { proposalId: string; as: "ceo" | "peer" | "committee" }) {
  const router = useRouter();
  const id = useId();
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  return (
    <form
      className="stack-form"
      onSubmit={async (e) => {
        e.preventDefault();
        const res = await fetch(`/api/ones/proposals/${proposalId}/messages`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ from: as, text }),
        }).catch(() => null);
        if (res?.ok) {
          router.refresh();
          return;
        }
        const code = res
          ? String(((await res.json().catch(() => ({}))) as { error?: string }).error ?? "")
          : "";
        setError(ERRORS[code] ?? NOT_SAVED);
      }}
    >
      <label htmlFor={id}>{LABEL}</label>
      <p className="hint" id={`${id}-hint`}>
        {HINT}
      </p>
      <textarea
        id={id}
        rows={4}
        maxLength={600}
        value={text}
        onChange={(e) => setText(e.target.value)}
        aria-describedby={`${id}-hint${error ? ` ${id}-err` : ""}`}
        aria-invalid={error ? true : undefined}
      />
      {error ? (
        <p className="field-error" id={`${id}-err`} role="alert">
          {error}
        </p>
      ) : null}
      <div className="actions">
        <button type="submit" className="button">
          {SEND}
        </button>
      </div>
    </form>
  );
}
