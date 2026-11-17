"use client";

/**
 * The S1 to S3 experiments on the admin page (L-AUDIT.flags, P-DECISIONS.experiments; BLD-A216): each one's state
 * and the share of people who see the other version, and one person put on a version by hand. Every change needs a
 * reason and is recorded. Admins only; the server checks it again.
 */
import { useCallback, useId, useState } from "react";

import { FieldError } from "./programme";
import { send, type Problem } from "./send";

export type Flag = {
  key: string;
  description: string;
  state: "on" | "off";
  alternative_percent: number;
  changed_at: string;
  people: Array<{ user_id: string; name: string; email: string; variant: "default" | "alternative" }>;
  exposures: { default: number; alternative: number };
};

const count = new Intl.NumberFormat("en-IN");

export function Flags({ initial }: { initial: Flag[] }) {
  const id = useId();
  const [flags, setFlags] = useState<Flag[]>(initial);
  const [message, setMessage] = useState("");
  const reload = useCallback(async (text: string) => {
    setMessage(text);
    const res = await fetch("/api/admin/flags", { cache: "no-store" });
    if (res.ok) setFlags(((await res.json()) as { flags: Flag[] }).flags);
  }, []);

  return (
    <section aria-labelledby={`${id}-title`} id="flags">
      <h2 id={`${id}-title`}>Experiments</h2>
      <p className="muted">
        Each experiment shows some people another version of a screen. Choose the share who see the other
        version, or put one person on a version. Every change needs a reason and is recorded.
      </p>
      <p role="status" aria-live="polite" className="sr-status">
        {message}
      </p>
      {flags.map((f) => (
        <FlagForm key={f.key} flag={f} onDone={reload} />
      ))}
    </section>
  );
}

function FlagForm({ flag, onDone }: { flag: Flag; onDone: (m: string) => Promise<void> }) {
  const id = useId();
  const name = flag.key.toUpperCase();
  const [state, setState] = useState<"on" | "off">(flag.state);
  const [percent, setPercent] = useState(String(flag.alternative_percent));
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const err = (field: string) =>
    problem && (problem.field ?? "form") === field
      ? { "aria-invalid": true as const, "aria-describedby": `${id}-err-${field}` }
      : {};

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const out = await send("PUT", `/api/admin/flags/${flag.key}`, {
      state,
      alternative_percent: Number(percent),
      reason,
    });
    if (!out.ok) return setProblem(out.problem);
    setProblem(null);
    setReason("");
    await onDone(`${name} saved.`);
  }

  return (
    <div className="stack-form" role="group" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`}>{name}</h3>
      <p>{flag.description}</p>
      <p className="muted">
        Seen so far: {count.format(flag.exposures.default)} on the usual version,{" "}
        {count.format(flag.exposures.alternative)} on the other.
      </p>
      <form onSubmit={submit} noValidate className="stack-form" aria-label={`Change ${name}`}>
        <FieldError id={`${id}-err-form`} problem={problem} field="form" />
        <fieldset>
          <legend>State</legend>
          {(["on", "off"] as const).map((v) => (
            <label key={v} className="choice">
              <input
                type="radio"
                name={`${id}-state`}
                value={v}
                checked={state === v}
                onChange={() => setState(v)}
              />{" "}
              {v === "on" ? "On" : "Off: everyone sees the usual version"}
            </label>
          ))}
        </fieldset>
        <FieldError id={`${id}-err-state`} problem={problem} field="state" />
        <label htmlFor={`${id}-percent`}>Share who see the other version (0 to 100 per cent)</label>
        <input
          id={`${id}-percent`}
          inputMode="numeric"
          value={percent}
          onChange={(e) => setPercent(e.target.value)}
          autoComplete="off"
          {...err("alternative_percent")}
        />
        <FieldError id={`${id}-err-alternative_percent`} problem={problem} field="alternative_percent" />
        <label htmlFor={`${id}-reason`}>Reason</label>
        <textarea
          id={`${id}-reason`}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={2}
          {...err("reason")}
        />
        <FieldError id={`${id}-err-reason`} problem={problem} field="reason" />
        <div className="actions">
          <button type="submit" className="button">
            Save {name}
          </button>
        </div>
      </form>
      <People flag={flag} onDone={onDone} />
    </div>
  );
}

function People({ flag, onDone }: { flag: Flag; onDone: (m: string) => Promise<void> }) {
  const id = useId();
  const name = flag.key.toUpperCase();
  const [email, setEmail] = useState("");
  const [variant, setVariant] = useState<"default" | "alternative" | "rule">("alternative");
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const err = (field: string) =>
    problem && (problem.field ?? "form") === field
      ? { "aria-invalid": true as const, "aria-describedby": `${id}-err-${field}` }
      : {};

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const out = await send("PUT", `/api/admin/flags/${flag.key}/people`, {
      email,
      variant: variant === "rule" ? null : variant,
      reason,
    });
    if (!out.ok) return setProblem(out.problem);
    setProblem(null);
    setEmail("");
    setReason("");
    await onDone(`${name}: ${email.trim()} saved.`);
  }

  return (
    <>
      {flag.people.length > 0 ? (
        <table className="table">
          <caption>People put on a version of {name} by hand</caption>
          <thead>
            <tr>
              <th scope="col">Person</th>
              <th scope="col">Version</th>
            </tr>
          </thead>
          <tbody>
            {flag.people.map((p) => (
              <tr key={p.user_id}>
                <th scope="row">
                  {p.name}
                  <div className="muted">{p.email}</div>
                </th>
                <td>{p.variant === "alternative" ? "The other version" : "The usual version"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      <form
        onSubmit={submit}
        noValidate
        className="stack-form"
        aria-label={`Put one person on a version of ${name}`}
      >
        <FieldError id={`${id}-err-form`} problem={problem} field="form" />
        <label htmlFor={`${id}-email`}>Work email</label>
        <input
          id={`${id}-email`}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="off"
          {...err("email")}
        />
        <FieldError id={`${id}-err-email`} problem={problem} field="email" />
        <label htmlFor={`${id}-variant`}>Version</label>
        <select
          id={`${id}-variant`}
          value={variant}
          onChange={(e) => setVariant(e.target.value as typeof variant)}
          {...err("variant")}
        >
          <option value="alternative">The other version</option>
          <option value="default">The usual version</option>
          <option value="rule">Back to the share</option>
        </select>
        <FieldError id={`${id}-err-variant`} problem={problem} field="variant" />
        <label htmlFor={`${id}-reason`}>Reason</label>
        <textarea
          id={`${id}-reason`}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={2}
          {...err("reason")}
        />
        <FieldError id={`${id}-err-reason`} problem={problem} field="reason" />
        <div className="actions">
          <button type="submit" className="button button-secondary">
            Save for this person
          </button>
        </div>
      </form>
    </>
  );
}
