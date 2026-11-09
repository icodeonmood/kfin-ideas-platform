"use client";

import { useId, useState } from "react";

import { Err, Status, useAction, useDone } from "../delivery/actions";

const LOOPS = [
  ["autonomy", "Acceptance of suggestions"],
  ["drift", "This week's report"],
  ["glossary", "New glossary terms"],
  ["canvas", "Last month's canvas report"],
  ["area_tags", "Area tag groups"],
  ["calibration", "Last quarter's results"],
] as const;

/** Approve or decline one proposal. The worker records who and when; nothing else changes. */
export function ProposalActions({ id }: { id: number }) {
  const { status, done } = useDone();
  const { error, busy, run } = useAction(done);
  const url = `/api/learning/proposals/${id}/decide`;
  return (
    <div>
      <div className="button-row">
        <button
          type="button"
          className="button"
          disabled={busy}
          onClick={() => run(url, { verdict: "approve" }, "Approved.")}
        >
          Approve
        </button>
        <button
          type="button"
          className="button button-secondary"
          disabled={busy}
          onClick={() => run(url, { verdict: "decline" }, "Declined.")}
        >
          Decline
        </button>
      </div>
      <Err text={error} />
      <Status text={status} />
    </div>
  );
}

export function RunLoop({ disabled }: { disabled: boolean }) {
  const { status, done } = useDone();
  const { error, busy, run } = useAction(done);
  const [kind, setKind] = useState("autonomy");
  const selectId = useId();
  return (
    <form
      className="inline-form"
      onSubmit={(e) => {
        e.preventDefault();
        void run("/api/learning/run", { kind }, "Done. The page shows the new numbers.");
      }}
    >
      <label htmlFor={selectId}>Report</label>
      <select id={selectId} value={kind} onChange={(e) => setKind(e.target.value)}>
        {LOOPS.map(([value, words]) => (
          <option key={value} value={value}>
            {words}
          </option>
        ))}
      </select>
      <button type="submit" className="button button-secondary" disabled={busy || disabled}>
        Run it now
      </button>
      {disabled ? <p className="hint">Learning jobs are switched off.</p> : null}
      <Err text={error} />
      <Status text={status} />
    </form>
  );
}
