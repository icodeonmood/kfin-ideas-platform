"use client";

import { useState } from "react";

import { teamUpOpener, useTeamUpSheet } from "@/components/teamup/teamup-sheet";

/** Synthetic: the pack's fictional idea and a made-up draft id. The e2e spec answers every call for them. */
const IDEA = "IDEA-2026-001412";
const TITLE = "Rejection SMS codes confuse investors";
const DRAFT = "7f1c2a9e-0b3d-4e5f-8a6b-1c2d3e4f5a6b";

/** Two hosts, as the screens will mount it: "Team up on …" on a tile, and the same from a draft on Check it. */
export function TeamUpDemo() {
  const [waiting, setWaiting] = useState<string | null>(null);
  const onIdea = useTeamUpSheet({ me: { initials: "KI" }, onSent: (s) => setWaiting(s.after?.line ?? null) });
  const onDraft = useTeamUpSheet({
    me: { initials: "KI" },
    draftId: DRAFT,
    draftTitle: "Failed SIP debit SMS gives no reason",
  });
  return (
    <div className="arrive kit">
      <h1 className="h1">Team up sheet</h1>
      <p className="lead">The team-up sheet with made-up content. Dev and test only.</p>
      <section className="card" aria-labelledby="k-teamup">
        <h2 id="k-teamup" className="h2">
          {TITLE}
        </h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 16 }}>
          {waiting ? (
            <button type="button" className="tb" {...teamUpOpener(IDEA)}>
              {waiting}
            </button>
          ) : (
            <button type="button" className="btn btn-primary" onClick={() => onIdea.open(IDEA)}>
              {`Team up on ${TITLE}`}
            </button>
          )}
          <button type="button" className="btn btn-secondary" onClick={() => onDraft.open(IDEA)}>
            Team up from your draft
          </button>
        </div>
      </section>
      {onIdea.sheet}
      {onDraft.sheet}
    </div>
  );
}
