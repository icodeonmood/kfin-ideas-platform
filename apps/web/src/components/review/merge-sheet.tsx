"use client";

/**
 * C-SHEET-MERGE: the review desk merges two similar ideas and can team the sharers up without a request
 * (L-MERGE.desk). A native dialog (top layer, the page behind made inert), mounted at the page root (S-R2.rules/5).
 * Its words come from the server for both lead choices, so the line follows the choice without a round trip.
 */
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldMsg } from "@/components/ui/field";
import type { DeskMergeResponse, MergeLead, MergeSheetResponse } from "@/lib/contracts";
import { sparkBurst } from "@/lib/motion/spark";

export function MergeSheet({
  ideaId,
  otherId,
  onClose,
  onMerged,
}: {
  ideaId: string;
  otherId: string;
  onClose: () => void;
  onMerged: (merged: DeskMergeResponse) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const [sheet, setSheet] = useState<MergeSheetResponse | null>(null);
  const [lead, setLead] = useState<MergeLead>("other");
  const [teamUp, setTeamUp] = useState(true);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    dialog.current?.showModal();
    let gone = false;
    (async () => {
      const res = await fetch(
        `/api/desk/ideas/${encodeURIComponent(ideaId)}/merge-sheet?other=${encodeURIComponent(otherId)}`,
      );
      if (!res.ok) {
        if (!gone) setError("This merge can’t be opened right now.");
        return;
      }
      const s = (await res.json()) as MergeSheetResponse;
      if (gone) return;
      setSheet(s);
      setLead(s.default_lead);
      setTeamUp(s.team_up.default);
      setNote(s.note.prefill);
    })();
    return () => {
      gone = true;
    };
  }, [ideaId, otherId]);

  async function merge() {
    if (!sheet) return;
    if (note.trim().length < sheet.note.min) {
      setError("Tell both why, in a line or two.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/desk/ideas/${encodeURIComponent(ideaId)}/merge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ other_idea_id: otherId, lead, team_up: teamUp, note: note.trim() }),
      });
      const body = (await res.json()) as DeskMergeResponse | { error: { message: string } };
      if (!res.ok || "error" in body) {
        setError(
          "error" in body ? body.error.message || "That didn’t merge. Try again." : "That didn’t merge.",
        );
        return;
      }
      // S-R2.rules/3: a merge fires the spark burst once, from the button, as the sheet closes
      if (button.current) sparkBurst(button.current);
      dialog.current?.close();
      onMerged(body);
    } catch {
      setError("That didn’t merge. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const refusal = sheet?.refusal[lead];
  return (
    <dialog
      ref={dialog}
      className="mgsheet"
      aria-labelledby="mgsheet-t"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === dialog.current) onClose(); // a click on the scrim
      }}
    >
      <button type="button" className="mgsheet-x" aria-label="Close without merging" onClick={onClose}>
        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
          <path
            d="M3.5 3.5l9 9M12.5 3.5l-9 9"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      </button>
      <h2 id="mgsheet-t" className="h3">
        {sheet?.title ?? `Merge with ${otherId}?`}
      </h2>
      {sheet ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void merge();
          }}
        >
          <p className="body">{sheet.by_lead[lead].line}</p>
          <fieldset className="mg-opts">
            <legend className="label">Which idea leads</legend>
            {sheet.options.map((o) => (
              <label key={o.lead} className={`mg-opt${lead === o.lead ? " on" : ""}`}>
                <input
                  type="radio"
                  name="lead"
                  value={o.lead}
                  checked={lead === o.lead}
                  onChange={() => setLead(o.lead)}
                />
                <span>
                  <strong>{o.label}</strong>
                  <span className="meta">{o.meta}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <label className="mg-team">
            <input type="checkbox" checked={teamUp} onChange={(e) => setTeamUp(e.target.checked)} />
            <span>
              <strong>{sheet.team_up.label}</strong>
              <span className="meta">{sheet.by_lead[lead].team_up}</span>
            </span>
          </label>
          <Field label={sheet.note.label} multiline error={error ?? undefined}>
            {(p) => (
              <textarea
                {...p}
                rows={3}
                maxLength={sheet.note.max}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            )}
          </Field>
          <p className="meta">{sheet.small_print}</p>
          {refusal ? <FieldMsg kind="warn">{refusal}</FieldMsg> : null}
          <div className="mg-actions">
            <Button
              ref={button}
              type="submit"
              variant="primary"
              busy={busy}
              busyLabel="Merging…"
              disabled={Boolean(refusal)}
            >
              {sheet.button}
            </Button>
          </div>
        </form>
      ) : error ? (
        <p className="fmsg" role="alert">
          {error}
        </p>
      ) : (
        <p className="meta" role="status">
          Getting the merge ready…
        </p>
      )}
    </dialog>
  );
}
