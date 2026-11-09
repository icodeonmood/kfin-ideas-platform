"use client";

/** "Run now" for the weekly grouping batch (§4.4 B); the run itself is a background job. */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

const ERRORS: Record<string, string> = {
  run_in_progress: "A run is already going. Proposals appear in the queue when it finishes.",
  switched_off: "Weekly grouping is switched off for now.",
};

export function RunNow() {
  const router = useRouter();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  async function run() {
    setBusy(true);
    const res = await fetch("/api/review/cluster-runs", { method: "POST" }).catch(() => null);
    const out = (await res?.json().catch(() => null)) as { error?: string } | null;
    setBusy(false);
    setMessage(
      res?.ok
        ? { text: "The run has started. Proposals appear in the queue when it finishes.", error: false }
        : { text: ERRORS[String(out?.error)] ?? "That did not go through. Please try again.", error: true },
    );
    statusRef.current?.focus();
    if (res?.ok) router.refresh();
  }
  return (
    <>
      <p
        ref={statusRef}
        tabIndex={-1}
        role="status"
        aria-live="polite"
        className={message?.error ? "field-error" : "muted"}
      >
        {message?.text ?? ""}
      </p>
      <button type="button" className="button button-secondary" disabled={busy} onClick={() => void run()}>
        Run the grouping now
      </button>
    </>
  );
}
