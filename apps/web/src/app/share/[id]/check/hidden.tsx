"use client";

/**
 * C-HIDDEN on Check it: the "Hidden from everyone" tile with the masked details ("Folio ••••89"), each with "Show it".
 * "Show it" asks why, one of three reasons (C-HIDDEN.list/1); the second "Show it" stays disabled until one is
 * picked (V-ACC.share/8); after showing, the row reads "Shown, because …" with "Hide it" to reverse (/3). Only the
 * masked form is ever on screen here. The question sits after the list, so the button that confirms is always the
 * last "Show it" on the part. After "Show it" confirms or "Hide it" swaps, focus moves to the row's new button
 * (WCAG 2.4.3); while one is saving, both wait.
 */
import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ChoiceChips } from "@/components/ui/chips";
import { FieldMsg } from "@/components/ui/field";
import { SHOW_REASON_LABEL, type HiddenDetail, type ShowReason } from "@/lib/contracts";

import { CHECK_COPY } from "./copy";

const C = CHECK_COPY.hidden;

/** The enum's words with the pack's curly apostrophe: "it’s made up for the example". */
export function reasonWords(reason: ShowReason): string {
  return SHOW_REASON_LABEL[reason].replace(/'/g, "’");
}

const REASONS = (Object.keys(SHOW_REASON_LABEL) as ShowReason[]).map((r) => ({
  value: r,
  label: reasonWords(r),
}));

export function HiddenTile({
  id,
  details,
  onShow,
  onHide,
}: {
  /** The phone's anchor for "1 detail hidden" (#pr-hidden). */
  id?: string;
  details: HiddenDetail[];
  onShow(id: string, reason: ShowReason): Promise<boolean>;
  onHide(id: string): Promise<boolean>;
}) {
  const [asking, setAsking] = useState<string | null>(null);
  const [reason, setReason] = useState<ShowReason | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  /** The row whose button was just swapped: its new button takes focus once it is drawn. */
  const [focusRow, setFocusRow] = useState<string | null>(null);
  const list = useRef<HTMLUListElement>(null);
  const askId = useId();

  useEffect(() => {
    if (!focusRow) return;
    const row = Array.from(list.current?.querySelectorAll<HTMLLIElement>("li[data-hid]") ?? []).find(
      (li) => li.dataset.hid === focusRow,
    );
    const b = row?.querySelector<HTMLButtonElement>("button");
    if (b) {
      b.focus();
      setFocusRow(null);
    }
  }, [focusRow, details]);

  if (!details.length) return null;
  const asked = details.find((d) => d.id === asking) ?? null;

  const confirm = async () => {
    if (!asked || !reason || busy) return;
    setBusy(true);
    const ok = await onShow(asked.id, reason);
    setBusy(false);
    setFailed(!ok);
    if (ok) {
      setAsking(null);
      setReason(null);
      setFocusRow(asked.id);
    }
  };

  const hide = async (rowId: string) => {
    if (busy) return;
    setBusy(true);
    const ok = await onHide(rowId);
    setBusy(false);
    setFailed(!ok);
    if (ok) setFocusRow(rowId);
  };

  return (
    <div className="ck-hid tile" id={id} tabIndex={id ? -1 : undefined}>
      <p className="ck-hid-t">{C.label}</p>
      <ul className="ck-hid-l" ref={list}>
        {details.map((d) => (
          <li key={d.id} data-hid={d.id}>
            <span className="ck-mask num">{d.masked}</span>
            {d.state === "shown" ? (
              <>
                <span className="ck-hid-why">{d.reason ? C.shown(reasonWords(d.reason)) : null}</span>
                <Button variant="text-blue" disabled={busy} onClick={() => void hide(d.id)}>
                  {C.hide}
                </Button>
              </>
            ) : (
              <Button
                variant="text-blue"
                aria-expanded={asking === d.id}
                aria-controls={asking === d.id ? askId : undefined}
                onClick={() => {
                  setAsking(asking === d.id ? null : d.id);
                  setReason(null);
                  setFailed(false);
                }}
              >
                {C.show}
              </Button>
            )}
          </li>
        ))}
      </ul>
      {asked ? (
        <div className="ck-hid-ask" id={askId}>
          <p className="ck-hid-q">{C.ask}</p>
          <ChoiceChips
            label={C.ask}
            options={REASONS}
            value={reason}
            onChange={(v) => setReason(v as ShowReason)}
          />
          <p className="meta">{C.note}</p>
          <div className="ck-hid-acts">
            <Button
              variant="text"
              onClick={() => {
                setAsking(null);
                setFocusRow(asked.id);
              }}
            >
              {C.keep}
            </Button>
            <Button size="sm" disabled={!reason} busy={busy} onClick={() => void confirm()}>
              {C.show}
            </Button>
          </div>
        </div>
      ) : null}
      {failed ? <FieldMsg>{CHECK_COPY.failed}</FieldMsg> : null}
    </div>
  );
}
