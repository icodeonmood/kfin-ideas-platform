"use client";

/** Whether the person's name may appear on the wall next to ideas they shared (`person_settings.show_name_on_wall`,
 * shown unless they hide it: DEC-104, BLD-E013). Names never appear anywhere else. */
import { useState } from "react";

export function NameOnWall({ initial }: { initial: boolean }) {
  const [on, setOn] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);

  async function change(next: boolean) {
    if (busy) return; // ignore clicks while saving; the box stays enabled so keyboard focus stays on it
    setBusy(true);
    setMessage(null);
    const res = await fetch("/api/me/comms-prefs", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name_on_wall: next }),
    }).catch(() => null);
    setBusy(false);
    if (res?.ok) {
      setOn(next);
      setMessage({
        text: next ? "Your name will show on the wall." : "Your name will not show on the wall.",
        error: false,
      });
    } else {
      setMessage({ text: "That did not go through. Please try again.", error: true });
    }
  }

  return (
    <section className="glass name-on-wall" aria-labelledby="mi-name">
      <h2 id="mi-name" className="t-h2">
        Your name on the wall
      </h2>
      <p>
        Ideas on the wall show a short summary, never your own words. You can also choose to show your name
        next to ideas you shared yourself, never ones you only joined. You can change this at any time.
      </p>
      <label className="check">
        <input
          type="checkbox"
          checked={on}
          aria-busy={busy}
          onChange={(e) => void change(e.target.checked)}
        />
        Show my name on the wall
      </label>
      <p role="status" aria-live="polite" className={message?.error ? "field-error" : "muted"}>
        {message?.text ?? ""}
      </p>
    </section>
  );
}
