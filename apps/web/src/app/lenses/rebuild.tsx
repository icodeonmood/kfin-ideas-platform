"use client";

import { Err, Status, useAction, useDone } from "../delivery/actions";

/** Admins can rebuild the lenses now instead of waiting for Monday morning. Audited by the worker. */
export function RebuildLenses() {
  const { status, done } = useDone();
  const { error, busy, run } = useAction(done);
  return (
    <div className="button-row">
      <button
        type="button"
        className="button button-secondary"
        disabled={busy}
        onClick={() => run("/api/lenses/rebuild", {}, "Lenses rebuilt.")}
      >
        Rebuild now
      </button>
      <Err text={error} />
      <Status text={status} />
    </div>
  );
}
