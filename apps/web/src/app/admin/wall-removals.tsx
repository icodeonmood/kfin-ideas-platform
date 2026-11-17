"use client";

/**
 * "Take off the Wall" (DEC-106, SHIP_PLAN_1PC §6.3): the review desk and admins take an idea's summary off the Wall
 * with a reason, and put it back. Both are recorded. The idea itself, its decision and its people are untouched.
 */
import { useId, useState } from "react";

import { FieldError, useConfirmStep, useHeadingFocus } from "./programme";
import { send, type Problem } from "./send";

export type Removal = { id: number; idea_ref: string; title: string; by: string; reason: string; at: string };

const when = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

export function WallRemovals({
  removals,
  onDone,
}: {
  removals: Removal[];
  onDone: (message: string) => Promise<void>;
}) {
  const id = useId();
  const { heading, then } = useHeadingFocus(onDone);
  const [ref, setRef] = useState("");
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const idea = ref.trim().toUpperCase();
    const out = await send("POST", `/api/admin/ideas/${encodeURIComponent(idea)}/wall-removal`, { reason });
    if (!out.ok) return setProblem(out.problem);
    setProblem(null);
    setRef("");
    setReason("");
    await onDone(`${idea} is off the Wall.`);
  }

  const err = (field: string) =>
    problem && (problem.field ?? "form") === field
      ? { "aria-invalid": true as const, "aria-describedby": `${id}-err-${field}` }
      : {};

  return (
    <section aria-labelledby={`${id}-title`} id="wall">
      <h2 id={`${id}-title`} ref={heading} tabIndex={-1}>
        Take an idea off the Wall
      </h2>
      <p className="muted">
        Use this when an idea&apos;s summary should not be on the Wall, for example if it is spam or
        sensitive. The idea, its decision and its people stay as they are. Every change needs a reason and is
        recorded.
      </p>
      <form onSubmit={submit} noValidate className="stack-form" aria-labelledby={`${id}-form`}>
        <h3 id={`${id}-form`}>Take off the Wall</h3>
        <FieldError id={`${id}-err-form`} problem={problem} field="form" />
        <label htmlFor={`${id}-idea`}>Idea reference</label>
        <p id={`${id}-idea-hint`} className="hint">
          For example, IDEA-2026-000123
        </p>
        <input
          id={`${id}-idea`}
          value={ref}
          onChange={(e) => setRef(e.target.value)}
          autoComplete="off"
          aria-invalid={problem?.field === "idea" ? true : undefined}
          aria-describedby={problem?.field === "idea" ? `${id}-idea-hint ${id}-err-idea` : `${id}-idea-hint`}
        />
        <FieldError id={`${id}-err-idea`} problem={problem} field="idea" />
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
            Take off the Wall
          </button>
        </div>
      </form>
      <h3>Off the Wall now</h3>
      {removals.length === 0 ? (
        <p>No idea is off the Wall.</p>
      ) : (
        <table className="table">
          <caption className="visually-hidden">Ideas off the Wall now</caption>
          <thead>
            <tr>
              <th scope="col">Idea</th>
              <th scope="col">Taken off by</th>
              <th scope="col">Reason</th>
              <th scope="col">When</th>
              <th scope="col">Put back</th>
            </tr>
          </thead>
          <tbody>
            {removals.map((r) => (
              <tr key={r.id}>
                <th scope="row">
                  {r.idea_ref}
                  <div className="muted">{r.title}</div>
                </th>
                <td>{r.by}</td>
                <td>{r.reason}</td>
                <td>{when.format(new Date(r.at))}</td>
                <td>
                  <PutBack removal={r} onDone={then} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function PutBack({ removal, onDone }: { removal: Removal; onDone: (m: string) => Promise<void> }) {
  const id = useId();
  // Opening moves focus to the reason, the step's first field; Cancel brings it back (WCAG 2.4.3).
  const { open, trigger, step, show, cancel, close } = useConfirmStep<HTMLTextAreaElement>();
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  if (!open)
    return (
      <button type="button" className="button button-secondary" ref={trigger} onClick={show}>
        Put back<span className="visually-hidden">: {removal.idea_ref}</span>
      </button>
    );
  return (
    <form
      noValidate
      className="inline-form"
      onSubmit={async (event) => {
        event.preventDefault();
        const out = await send("DELETE", `/api/admin/ideas/${removal.idea_ref}/wall-removal`, { reason });
        if (!out.ok) return setProblem(out.problem);
        close();
        await onDone(`${removal.idea_ref} is back on the Wall.`);
      }}
    >
      <label htmlFor={`${id}-reason`}>Reason for putting it back</label>
      <textarea
        id={`${id}-reason`}
        ref={step}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={2}
        aria-invalid={problem ? true : undefined}
        aria-describedby={problem ? `${id}-err` : undefined}
      />
      {problem ? (
        <p id={`${id}-err`} role="alert" className="field-error">
          {problem.message}
        </p>
      ) : null}
      <div className="actions">
        <button type="submit" className="button">
          Put back on the Wall
        </button>
        <button type="button" className="button button-secondary" onClick={cancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
