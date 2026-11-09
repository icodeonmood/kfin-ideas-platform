"use client";

import { useId, useState } from "react";

import { Err, Status, useAction, useDone } from "../delivery/actions";

const LOOPS = [
  ["autonomy", "Acceptance of suggestions"],
  ["drift", "This week's report"],
  ["glossary", "New glossary terms"],
  ["role_themes", "Friction themes by role"],
  ["canvas", "Last month's canvas report"],
  ["area_tags", "Area tag groups"],
  ["calibration", "Last quarter's results"],
] as const;

/** Approve or decline one proposal (or one role's friction themes). The worker records who and when; nothing
 * else changes. */
export function ProposalActions({
  id,
  path = "proposals",
}: {
  id: number;
  path?: "proposals" | "role-themes";
}) {
  const { status, done } = useDone();
  const { error, busy, run } = useAction(done);
  const url = `/api/learning/${path}/${id}/decide`;
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

/** Write an approved term or tag into the company repo (BLD-136). Everyone will be able to read it, so the words
 * are checked like any public text; the repo writer then writes the file from the outbox. */
export function PublishProposal({
  id,
  kind,
  term,
}: {
  id: number;
  kind: "glossary_term" | "area_tag";
  term: string | null;
}) {
  const { status, done } = useDone();
  const { error, busy, run } = useAction(done);
  const [open, setOpen] = useState(false);
  const [definition, setDefinition] = useState("");
  const [aliases, setAliases] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const ids = { a: useId(), b: useId(), hint: useId() };
  if (!open)
    return (
      <div>
        <button type="button" className="button button-secondary" onClick={() => setOpen(true)}>
          Write it into the company repo
        </button>
        <Status text={status} />
      </div>
    );
  const glossary = kind === "glossary_term";
  return (
    <form
      className="stack-form"
      onSubmit={(e) => {
        e.preventDefault();
        void run(
          `/api/learning/proposals/${id}/publish`,
          glossary ? { definition, aliases } : { title, description },
          "Queued. The company repo gets the file within a minute.",
        ).then((ok) => ok && setOpen(false));
      }}
    >
      <p id={ids.hint} className="hint">
        Everyone can read this once it is written. No names of colleagues or clients.
      </p>
      {glossary ? (
        <>
          <label htmlFor={ids.a}>What {term ?? "the term"} means</label>
          <textarea
            id={ids.a}
            rows={3}
            maxLength={400}
            aria-describedby={ids.hint}
            value={definition}
            onChange={(e) => setDefinition(e.target.value)}
          />
          <label htmlFor={ids.b}>Other ways people write it (optional, separated by commas)</label>
          <input
            id={ids.b}
            type="text"
            maxLength={300}
            value={aliases}
            onChange={(e) => setAliases(e.target.value)}
          />
        </>
      ) : (
        <>
          <label htmlFor={ids.a}>Name of the area tag</label>
          <input
            id={ids.a}
            type="text"
            maxLength={40}
            aria-describedby={ids.hint}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <label htmlFor={ids.b}>What it covers</label>
          <textarea
            id={ids.b}
            rows={3}
            maxLength={300}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </>
      )}
      <div className="button-row">
        <button type="submit" className="button" disabled={busy} aria-busy={busy}>
          Write it
        </button>
        <button type="button" className="button button-secondary" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
      <Err text={error} />
    </form>
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
