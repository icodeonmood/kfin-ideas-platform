"use client";

import { useEffect, useId, useRef, type CSSProperties } from "react";

import type { TierMoment } from "@/lib/contracts/api";

import { rememberUnsentSeen, takeUnsentSeen } from "./rules";

/** This browser's storage, or null where it is blocked. */
export function deviceStore(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Marks the moment seen; true once the worker has it (S-ONE.rules/3). */
export async function markSeen(id: TierMoment["id"]): Promise<boolean> {
  const res = await fetch(`/api/one/glow-up/${encodeURIComponent(String(id))}/seen`, {
    method: "POST",
  }).catch(() => null);
  return Boolean(res?.ok);
}

/**
 * S-ONE.states `showGlowUp`, L-ONES.rules/3: the full-screen moment over the dashboard when a tier has just risen.
 * "No. 17, your spark is hotter", "From Tier 1, Spark to Tier 2, Glow", "Your story so far", "Messages for you" and
 * "Back to my dashboard". A modal dialog: focus moves to its title on open, Escape closes it, the page behind is
 * inert. It plays once: it is marked seen as soon as it shows (S-ONE.rules/3). A "seen" that does not land is
 * remembered on this device, and the next load sends it once more and leaves the dialog closed instead of playing
 * the moment again. Under reduced motion it appears already settled (one.css).
 */
export function GlowUp({
  moment,
  number,
  onClose,
}: {
  moment: TierMoment;
  number: number;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const titleId = useId();
  const marked = useRef(false);
  /** Decided once per moment on arrival: it already played here and only its "seen" is owed. */
  const owed = useRef<boolean | null>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    owed.current ??= takeUnsentSeen(deviceStore(), moment.id);
    if (owed.current) {
      if (!marked.current) {
        marked.current = true;
        void markSeen(moment.id); // once: a second miss lets the moment play on the load after
      }
      return;
    }
    if (!d.open) d.showModal();
    title.current?.focus();
    if (!marked.current) {
      marked.current = true;
      void markSeen(moment.id).then((ok) => {
        if (!ok) rememberUnsentSeen(deviceStore(), moment.id);
      });
    }
    return () => {
      if (d.open) d.close();
    };
  }, [moment.id]);

  const close = () => {
    ref.current?.close();
    onClose();
  };

  return (
    <dialog
      ref={ref}
      className="on-moment"
      aria-labelledby={titleId}
      style={{ "--on-to": `var(--tier-${moment.to})` } as CSSProperties}
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
    >
      <div className="on-moment-glow" aria-hidden="true" />
      <div className="on-moment-in">
        <div className="on-flag on-flag-left">
          <span className="on-bar on-heat" aria-hidden="true" />
          <p className="on-ebd">{`${moment.from_label} to ${moment.to_label}`}</p>
        </div>
        <p className="num on-moment-no" aria-hidden="true">
          {number}
        </p>
        <h2 id={titleId} ref={title} tabIndex={-1} className="d2 on-moment-t">
          {moment.title}
        </h2>
        <p className="on-moment-line">
          From {moment.from_label} to <strong>{moment.to_label}</strong>
        </p>
        <div className="on-moment-story">
          <h3 className="on-ebd on-white">Your story so far</h3>
          <dl className="on-story">
            <div>
              <dt>Ideas shared</dt>
              <dd className="num">{moment.story.shared}</dd>
            </div>
            <div>
              <dt>Picked or being built</dt>
              <dd className="num">{moment.story.picked}</dd>
            </div>
            <div>
              <dt>Shipped</dt>
              <dd className="num">{moment.story.shipped}</dd>
            </div>
          </dl>
          {moment.messages.length ? (
            <>
              <h3 className="on-ebd on-white on-msgs-h">Messages for you</h3>
              {moment.messages.map((m, i) => (
                <figure key={i} className="on-msg">
                  <blockquote>{m.text}</blockquote>
                  <figcaption>{m.from_label}</figcaption>
                </figure>
              ))}
            </>
          ) : null}
        </div>
        <div className="on-moment-act">
          <button type="button" className="btn on-wbtn" onClick={close}>
            Back to my dashboard
          </button>
        </div>
      </div>
    </dialog>
  );
}
