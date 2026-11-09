"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

const ERRORS: Record<string, string> = {
  personal_data: "Please take out any personal details (numbers, addresses, investor names).",
  text_too_short: "Please write at least a short sentence.",
  text_too_long: "Please keep it under 600 characters.",
  already_written: "You've already written a message for this.",
  checks_unavailable: "We can't check text just now. Please try again in a few minutes.",
};

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
        setError(ERRORS[code] ?? "That didn't save. Please try again.");
      }}
    >
      <label htmlFor={id}>Your message</label>
      <p className="hint" id={`${id}-hint`}>
        A few sentences. What did they do that mattered? No personal details.
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
          Send your message
        </button>
      </div>
    </form>
  );
}
