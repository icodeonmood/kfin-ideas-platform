"use client";

/**
 * The glow-up (DEC-084): plays once, the first time a One signs in after a tier change. The spark heats from the
 * old tier colour to the new one, then their story so far and the messages written for them. A native modal
 * dialog, so focus, Escape and the page behind it behave; reduced motion shows the end state at once.
 */
import { useEffect, useRef, useState } from "react";

import { OneSpark } from "@/components/one-spark";
import { day } from "@/lib/dates";
import { measureList } from "@/lib/measures";
import type { GlowUp as Glow } from "@/server/ones";

const HEAT_MS = 2600;
const FROM_WORDS = {
  committee: "From the core committee",
  ceo: "From the CEO",
  peer: "From a colleague",
} as const;

export function GlowUp({
  glow,
  number,
  inductionNo,
}: {
  glow: Glow;
  number: number | null;
  inductionNo: number;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [hot, setHot] = useState(false);
  const [told, setTold] = useState(false);

  useEffect(() => {
    const d = dialog.current;
    if (!d) return;
    if (!d.open) d.showModal();
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const heat = window.setTimeout(() => setHot(true), reduced ? 0 : 400);
    const tell = window.setTimeout(() => setTold(true), reduced ? 0 : HEAT_MS + 600);
    return () => {
      window.clearTimeout(heat);
      window.clearTimeout(tell);
    };
  }, []);

  async function close() {
    await fetch(`/api/me/one/glow-up/${glow.id}/seen`, { method: "POST" }).catch(() => null);
    dialog.current?.close();
  }

  const colour = hot ? glow.to.tier_colour : glow.from.tier_colour;
  const measures = measureList(glow.story.measures);
  return (
    <dialog
      ref={dialog}
      className="glow-up"
      data-theme="zed"
      data-tier={String(Math.min(7, Math.max(1, hot ? glow.to.tier : glow.from.tier)))}
      aria-labelledby="glow-title"
      onCancel={(e) => {
        e.preventDefault();
        void close();
      }}
    >
      <div className="glow-hero">
        <div className="glow-spark">
          <OneSpark inductionNo={inductionNo} colour={colour} size={120} zeros />
        </div>
        <p className="glow-num" aria-hidden="true">
          {number}
        </p>
      </div>
      <h2 id="glow-title" tabIndex={-1}>
        {glow.up ? `No. ${number}, your spark is hotter` : `No. ${number}, your tier has changed`}
      </h2>
      <p className="glow-from">
        From Tier {glow.from.tier}, {glow.from.tier_name} to{" "}
        <strong>
          Tier {glow.to.tier}, {glow.to.tier_name}
        </strong>
      </p>
      <div aria-live="polite">
        {told ? (
          <div className="story">
            <h3>Your story so far</h3>
            <dl className="story-counts">
              <div>
                <dt>Ideas shared</dt>
                <dd>{glow.story.ideas_shared}</dd>
              </div>
              <div>
                <dt>Picked or being built</dt>
                <dd>{glow.story.ideas_picked}</dd>
              </div>
              <div>
                <dt>Shipped</dt>
                <dd>{glow.story.ideas_shipped}</dd>
              </div>
            </dl>
            {measures.length ? (
              <ul className="jersey-measures" aria-label="Impact so far">
                {measures.map(([label, words]) => (
                  <li key={label}>
                    <span>{label}:</span> {words}
                  </li>
                ))}
              </ul>
            ) : null}
            <ol>
              {glow.story.milestones.map((m, i) => (
                <li key={i}>
                  {m.on ? `${day(m.on)}: ` : ""}
                  {m.what}
                </li>
              ))}
            </ol>
            {glow.messages.length ? <h3>Messages for you</h3> : null}
            {glow.messages.map((m, i) => (
              <figure key={i} className="glow-message">
                <blockquote>{m.text}</blockquote>
                <figcaption className="glow-from">
                  {FROM_WORDS[m.from]}: {m.name}
                </figcaption>
              </figure>
            ))}
          </div>
        ) : null}
      </div>
      <div className="btn-row glow-actions">
        <button type="button" className="btn btn-primary btn-lg" onClick={() => void close()}>
          {told ? "Back to my dashboard" : "Skip to my dashboard"}
        </button>
      </div>
    </dialog>
  );
}
