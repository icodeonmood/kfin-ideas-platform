"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

const ERRORS: Record<string, string> = {
  text_too_short: "Please give a reason of at least 10 characters.",
  veto_window_closed: "The 5 working days to reconsider have passed.",
  personal_data: "Please take out personal details from the reason.",
};

export function VetoForm({ itemId, until }: { itemId: number; until: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const fieldRef = useRef<HTMLTextAreaElement>(null);

  async function veto(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const res = await fetch(`/api/review/items/${itemId}/veto`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    }).catch(() => null);
    const out = (await res?.json().catch(() => null)) as { error?: string } | null;
    setBusy(false);
    if (!res?.ok) {
      setError(ERRORS[String(out?.error)] ?? "That did not go through. Please try again.");
      fieldRef.current?.focus();
      return;
    }
    router.push(`/review/${itemId}`);
  }

  if (!open)
    return (
      <button
        type="button"
        className="button button-secondary"
        aria-expanded={false}
        aria-controls={`veto-${itemId}`}
        onClick={() => {
          setOpen(true);
          requestAnimationFrame(() => fieldRef.current?.focus());
        }}
      >
        Reconsider this (until {until})
      </button>
    );
  return (
    <form id={`veto-${itemId}`} onSubmit={(e) => void veto(e)}>
      <div className="field">
        <label htmlFor={`veto-reason-${itemId}`}>Why the committee should reconsider</label>
        <textarea
          ref={fieldRef}
          id={`veto-reason-${itemId}`}
          rows={3}
          value={reason}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `veto-error-${itemId}` : undefined}
          onChange={(e) => setReason(e.target.value)}
        />
        {error ? (
          <p id={`veto-error-${itemId}`} className="field-error" role="alert">
            {error}
          </p>
        ) : null}
      </div>
      <button type="submit" className="button" disabled={busy}>
        Take it back to decide myself
      </button>
    </form>
  );
}
