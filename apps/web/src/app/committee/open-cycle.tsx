"use client";

/** The chair opens this month's cycle: every qualified group joins a review for its committee (§4.6 step 1). */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

export function OpenCycle() {
  const router = useRouter();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [slots, setSlots] = useState("8");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  async function open() {
    setBusy(true);
    const res = await fetch("/api/committee/cycles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ presentation_slots: Number(slots) }),
    }).catch(() => null);
    const out = (await res?.json().catch(() => null)) as { cycle_id?: string; rounds?: string[] } | null;
    setBusy(false);
    setMessage(
      res?.ok
        ? { text: `Cycle ${out?.cycle_id} is open with ${out?.rounds?.length ?? 0} reviews.`, error: false }
        : { text: "That did not go through. Please try again.", error: true },
    );
    statusRef.current?.focus();
    if (res?.ok) router.refresh();
  }
  return (
    <section aria-labelledby="c-open" className="panel">
      <h2 id="c-open">Open this month&apos;s cycle</h2>
      <p
        ref={statusRef}
        tabIndex={-1}
        role="status"
        aria-live="polite"
        className={message?.error ? "field-error" : "muted"}
      >
        {message?.text ?? ""}
      </p>
      <div className="field">
        <label htmlFor="c-slots">Presentation slots this cycle</label>
        <input id="c-slots" inputMode="numeric" value={slots} onChange={(e) => setSlots(e.target.value)} />
      </div>
      <button type="button" className="button" disabled={busy} onClick={() => void open()}>
        Open the cycle
      </button>
    </section>
  );
}
