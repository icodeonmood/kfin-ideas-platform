"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { recordText, SHOWCASE_LABELS } from "@/components/showcase-view";
import { buttonClass } from "@/components/ui/button";
import { Field, FieldMsg } from "@/components/ui/field";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import type { ShowcaseBrief } from "@/server/ones";

/** The words the retired /my-ideas/showcase page used, kept as they were (BLD-E042). */
const LEAD =
  "Thirty minutes at The Showcase, in seven parts. Parts you leave empty show what your record says. The core committee reads this before the event.";
const SAVED = "Saved. The committee sees your latest version.";
// NOT DRAWN (BLD-E042): HR sign-off
const LOAD_FAILED = "We can't load your Showcase brief just now. Please try again in a minute.";
// NOT DRAWN (BLD-E042): HR sign-off
const CLOSE = "Close";
const ERRORS: Record<string, string> = {
  personal_data: "Please take out any personal details (numbers, addresses, investor names) and try again.",
  text_needs_review: "Please reword this: it reads as off-topic or unkind, so we can't save it as it is.",
  names_not_allowed: "Leave out the names of colleagues and clients: everyone will see this.",
  text_too_long: "Please keep each part under 600 characters.",
  checks_unavailable: "We can't check text just now. Please try again in a few minutes.",
};

/**
 * "Your Showcase brief" (S-ONE.layout/6; DEC-086, kept by DEC-106 (4)). The board links it to the dashboard itself,
 * so it opens here as a sheet over S-ONE (BLD-E042): the seven parts from `GET /api/me/one/showcase`, saved with
 * `PUT`. Focus moves inside on open, Escape closes it and focus returns to its link (V-ACC.visual/11).
 */
export function ShowcaseSheet({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const titleId = useId();
  const [brief, setBrief] = useState<ShowcaseBrief | null>(null);
  const [failed, setFailed] = useState(false);
  const [parts, setParts] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
    title.current?.focus();
    return () => {
      if (d?.open) d.close();
    };
  }, []);

  useEffect(() => {
    const ask = new AbortController();
    fetch("/api/me/one/showcase", { signal: ask.signal, cache: "no-store" })
      .then((r) => (r.ok ? (r.json() as Promise<ShowcaseBrief>) : null))
      .then((b) => {
        if (!b) return setFailed(true);
        setBrief(b);
        setParts(Object.fromEntries(b.parts.map((p) => [p.key, p.own])));
      })
      .catch(() => {
        if (!ask.signal.aborted) setFailed(true);
      });
    return () => ask.abort();
  }, []);

  const close = () => {
    ref.current?.close();
    onClose();
  };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setStatus("");
    const res = await fetch("/api/me/one/showcase", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parts),
    }).catch(() => null);
    setBusy(false);
    if (res?.ok) {
      setStatus(SAVED);
      return;
    }
    const code = res ? String(((await res.json().catch(() => ({}))) as { error?: unknown }).error ?? "") : "";
    setError(ERRORS[code] ?? "Couldn't save that. Try again.");
  };

  return (
    <dialog
      ref={ref}
      className="on-sheet"
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
    >
      <div className="on-sheet-top">
        <h2 id={titleId} ref={title} tabIndex={-1} className="h2">
          Your Showcase brief
        </h2>
        <button type="button" className={buttonClass("text")} onClick={close}>
          {CLOSE}
        </button>
      </div>
      <p className="body">{LEAD}</p>
      {failed ? (
        <p className="body on-sheet-fail">{LOAD_FAILED}</p>
      ) : !brief ? (
        <Loading what="Loading your Showcase brief">
          <div className="on-sheet-sk">
            <Skeleton width="40%" height={16} />
            <Skeleton height={72} />
            <Skeleton width="40%" height={16} />
            <Skeleton height={72} />
          </div>
        </Loading>
      ) : (
        <form className="on-sheet-form" onSubmit={save} noValidate>
          {brief.parts.map((p) => {
            const record = recordText(brief, p.key, p.from_record);
            const ask = SHOWCASE_LABELS[p.key]?.ask ?? "";
            return (
              <Field
                key={p.key}
                label={SHOWCASE_LABELS[p.key]?.title ?? p.key}
                optional
                help={record ? `${ask} Your record says: ${record}` : ask}
                multiline
              >
                {(ctl) => (
                  <textarea
                    {...ctl}
                    rows={3}
                    maxLength={600}
                    value={parts[p.key] ?? ""}
                    onChange={(e) => setParts((x) => ({ ...x, [p.key]: e.target.value }))}
                  />
                )}
              </Field>
            );
          })}
          {error ? <FieldMsg>{error}</FieldMsg> : null}
          <p className="body on-saved" role="status">
            {status}
          </p>
          <div className="btn-row on-sheet-act">
            <button type="submit" className={buttonClass("primary")} aria-busy={busy || undefined}>
              Save your brief
            </button>
          </div>
        </form>
      )}
    </dialog>
  );
}
