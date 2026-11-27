"use client";

import { useCallback, useId, useState } from "react";

export type Switch = {
  name: string;
  state: "on" | "off";
  reason: string | null;
  changed_by: string | null;
  changed_at: string;
  can_flip: boolean;
};

const REASON_MIN = 10;

/** What a refused change says. New words, under BUILD_LOG "To confirm later" (BLD-F111, DEC-143 (h)). */
export const KILL_SWITCH_COPY = {
  failed: "That didn't work. You may not have permission to change this switch.",
  noModelRoute:
    "ai.all can't be switched on: this server has no model route yet. Set the route first (docs/UAT.md, Switching to full mode), then try again.",
  routeUnchecked:
    "We couldn't check this server's model route, so ai.all stays off. Please try again in a few minutes.",
} as const;

/** The line for a refused change, from the route's error code. */
export function refusedLine(error: unknown): string {
  if (error === "no_model_route") return KILL_SWITCH_COPY.noModelRoute;
  if (error === "route_unchecked") return KILL_SWITCH_COPY.routeUnchecked;
  return KILL_SWITCH_COPY.failed;
}

export function KillSwitches({ initial }: { initial: Switch[] }) {
  const [switches, setSwitches] = useState<Switch[]>(initial);
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    const res = await fetch("/api/admin/kill-switches", { cache: "no-store" });
    if (res.ok) setSwitches(((await res.json()) as { switches: Switch[] }).switches);
  }, []);

  return (
    <section aria-labelledby="ks-title">
      <h2 id="ks-title">Kill switches</h2>
      <p className="muted">
        Turning a switch off stops that feature for everyone within 10 seconds. Every change needs a reason
        and is recorded.
      </p>
      <p role="status" aria-live="polite" className="sr-status">
        {message}
      </p>
      {
        <table className="table">
          <caption className="visually-hidden">Kill switches and their state</caption>
          <thead>
            <tr>
              <th scope="col">Switch</th>
              <th scope="col">State</th>
              <th scope="col">Last change</th>
              <th scope="col">Change</th>
            </tr>
          </thead>
          <tbody>
            {switches.map((s) => (
              <SwitchRow
                key={s.name}
                s={s}
                onDone={async (text) => {
                  setMessage(text);
                  await load();
                }}
              />
            ))}
          </tbody>
        </table>
      }
    </section>
  );
}

function SwitchRow({ s, onDone }: { s: Switch; onDone: (message: string) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const id = useId();
  const target = s.state === "on" ? "off" : "on";
  const action = target === "off" ? "Switch off" : "Switch on";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (reason.trim().length < REASON_MIN) {
      setError(`Please give a reason of at least ${REASON_MIN} characters.`);
      return;
    }
    const res = await fetch("/api/admin/kill-switches", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: s.name, state: target, reason }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as { error?: unknown };
      setError(refusedLine(body.error));
      return;
    }
    setOpen(false);
    setReason("");
    setError("");
    await onDone(`${s.name} is now ${target}.`);
  }

  return (
    <tr>
      <th scope="row">
        <code>{s.name}</code>
      </th>
      <td>
        <span className={`state state-${s.state}`}>{s.state === "on" ? "On" : "Off"}</span>
      </td>
      <td>
        {s.changed_by
          ? new Date(s.changed_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
          : "Never changed"}
        {s.reason ? <div className="muted">{s.reason}</div> : null}
      </td>
      <td>
        {!s.can_flip ? (
          <span className="muted">Not yours to change</span>
        ) : open ? (
          <form onSubmit={submit} noValidate className="inline-form">
            <label htmlFor={`${id}-reason`}>Reason for this change</label>
            <textarea
              id={`${id}-reason`}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? `${id}-error` : undefined}
              rows={2}
              required
            />
            {error ? (
              <p id={`${id}-error`} className="field-error">
                {error}
              </p>
            ) : null}
            <div className="actions">
              <button type="submit" className="button">
                {action}
              </button>
              <button type="button" className="button button-secondary" onClick={() => setOpen(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <button
            type="button"
            className="button button-secondary"
            onClick={() => setOpen(true)}
            aria-label={`${action}: ${s.name}`}
          >
            {action}…
          </button>
        )}
      </td>
    </tr>
  );
}
