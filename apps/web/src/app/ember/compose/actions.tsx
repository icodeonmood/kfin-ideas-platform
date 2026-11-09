"use client";

import { useId, useState } from "react";

import { Err, Status, useAction, useDone } from "../../delivery/actions";

/** An admin opens this month's draft. */
export function StartDraft() {
  const { status, done } = useDone();
  const { error, busy, run } = useAction(done);
  return (
    <div>
      <button
        type="button"
        className="button"
        disabled={busy}
        aria-busy={busy}
        onClick={() => run("/api/ember/drafts", {}, "This month's draft is open.")}
      >
        Start this month&apos;s issue
      </button>
      <Err text={error} />
      <Status text={status} />
    </div>
  );
}

/** The chair writes "What the committee looks for": checked like anything everyone will read. */
export function NoteForm({ id, initial }: { id: number; initial: string | null }) {
  const { status, done } = useDone();
  const { error, busy, run } = useAction(done);
  const [note, setNote] = useState(initial ?? "");
  const fieldId = useId();
  const hintId = useId();
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void run(`/api/ember/${id}/note`, { note }, "Note saved.", "PUT");
      }}
    >
      <label htmlFor={fieldId}>What the committee looks for</label>
      <p id={hintId} className="hint">
        Up to 90 words, from the chair. No names of colleagues or clients.
      </p>
      <textarea
        id={fieldId}
        aria-describedby={hintId}
        rows={4}
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
      <div className="button-row">
        <button type="submit" className="button button-secondary" disabled={busy} aria-busy={busy}>
          Save the note
        </button>
      </div>
      <Err text={error} />
      <Status text={status} />
    </form>
  );
}

/** The chair approves the note: only then can an admin who did not write it send the issue (BLD-134). */
export function ApproveNote({ id }: { id: number }) {
  const { status, done } = useDone();
  const { error, busy, run } = useAction(done);
  return (
    <div>
      <button
        type="button"
        className="button"
        disabled={busy}
        aria-busy={busy}
        onClick={() => run(`/api/ember/${id}/ready`, {}, "Approved. An admin can now send the issue.")}
      >
        Approve the note
      </button>
      <Err text={error} />
      <Status text={status} />
    </div>
  );
}

/** An admin sends the issue to everyone, in two steps so it can't go out by accident. The server checks the
 * chair's approval and the confirm token as well (BLD-134). */
export function SendIssue({
  id,
  blocked,
  confirmToken,
}: {
  id: number;
  blocked: string | null;
  confirmToken: string;
}) {
  const { status, done } = useDone();
  const { error, busy, run } = useAction(done);
  const [confirming, setConfirming] = useState(false);
  if (blocked) return <p className="notice">{blocked}</p>;
  return (
    <div>
      {confirming ? (
        <div className="button-row">
          <button
            type="button"
            className="button"
            disabled={busy}
            aria-busy={busy}
            onClick={() =>
              run(
                `/api/ember/${id}/send`,
                { confirm_token: confirmToken },
                "Sent. Everyone gets it in their inbox.",
              )
            }
          >
            Yes, send to everyone
          </button>
          <button type="button" className="button button-secondary" onClick={() => setConfirming(false)}>
            Not yet
          </button>
        </div>
      ) : (
        <button type="button" className="button" onClick={() => setConfirming(true)}>
          Send to everyone
        </button>
      )}
      <Err text={error} />
      <Status text={status} />
    </div>
  );
}
