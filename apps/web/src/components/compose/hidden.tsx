"use client";
/**
 * C-HIDDEN in the draft panel (BLD-C121): one folded bar, "Personal details hidden", the kinds and a count; it opens
 * to a list. Each row shows only the masked form. "Show it" asks why (three reasons, one choice) and stays disabled
 * until one is picked (V-FIELDS.tellit/8); after showing, the row says why, with "Hide it" to reverse. Focusing a row
 * underlines the matching phrase in the person's own text (`onFocusDetail`).
 */
import { useId, useState } from "react";

import { IconLock, IconChevron } from "@/components/compose/icons";
import { Button } from "@/components/ui/button";
import type { HiddenDetail, ShowReason } from "@/lib/contracts";
import { HIDDEN_COPY, KIND_LABEL, kindsLine, SHOW_REASONS, shownLine } from "@/lib/compose/hidden";

export type HiddenActions = {
  show(id: string, reason: ShowReason): Promise<void>;
  hide(id: string): Promise<void>;
};

export function HiddenDetails({
  details,
  actions,
  onFocusDetail,
}: {
  details: HiddenDetail[];
  actions: HiddenActions;
  onFocusDetail?: (id: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  if (!details.length) return null;
  const hidden = details.filter((d) => d.state === "hidden").length;
  return (
    <div className="hid hidg">
      <span className="vh">{HIDDEN_COPY.label}</span>
      <button
        type="button"
        className="hidb"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="hic" aria-hidden="true">
          <IconLock />
        </span>
        <span className="hbt">
          <b>{HIDDEN_COPY.bar}</b>
          <span>{kindsLine(details)}</span>
        </span>
        <span className="hcount">{hidden || details.length}</span>
        <IconChevron className="chev" />
      </button>
      {open ? (
        <ul className="hidl" id={listId}>
          {details.map((d) => (
            <HiddenRow key={d.id} detail={d} actions={actions} onFocusDetail={onFocusDetail} />
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function HiddenRow({
  detail,
  actions,
  onFocusDetail,
}: {
  detail: HiddenDetail;
  actions: HiddenActions;
  onFocusDetail?: (id: string | null) => void;
}) {
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState<ShowReason | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const qid = useId();
  const shown = detail.state === "shown";

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setFailed(null);
    try {
      await fn();
      setAsking(false);
      setReason(null);
    } catch (err) {
      setFailed(err instanceof Error && "text" in err && typeof err.text === "string" ? err.text : null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <li
      onFocus={() => onFocusDetail?.(detail.id)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) onFocusDetail?.(null);
      }}
      onMouseEnter={() => onFocusDetail?.(detail.id)}
      onMouseLeave={() => onFocusDetail?.(null)}
    >
      <div className="hrow">
        <span className="hkind">{KIND_LABEL[detail.kind] ?? detail.kind}</span>
        <span className="htx">
          <p className="hv">{detail.masked}</p>
          <p className="hs">{shown ? shownLine(detail.reason) : HIDDEN_COPY.status}</p>
        </span>
        {shown ? (
          <Button
            variant="line"
            size="sm"
            className="hbtn"
            busy={busy}
            onClick={() => run(() => actions.hide(detail.id))}
          >
            {HIDDEN_COPY.hide}
          </Button>
        ) : asking ? null : (
          <Button variant="line" size="sm" className="hbtn" onClick={() => setAsking(true)}>
            {HIDDEN_COPY.show}
          </Button>
        )}
      </div>
      {asking && !shown ? (
        <div className="hask" role="group" aria-labelledby={qid}>
          <p className="hq" id={qid}>
            {HIDDEN_COPY.question}
          </p>
          <div className="hopts" role="radiogroup" aria-labelledby={qid}>
            {SHOW_REASONS.map((r) => (
              <label key={r.value} className="hopt" data-checked={reason === r.value ? "" : undefined}>
                <input
                  type="radio"
                  className="vh"
                  name={qid}
                  value={r.value}
                  checked={reason === r.value}
                  onChange={() => setReason(r.value)}
                />
                <span className="rdot" aria-hidden="true" />
                {r.label}
              </label>
            ))}
          </div>
          <div className="hact">
            <span className="hnote">{HIDDEN_COPY.note}</span>
            <Button variant="text" onClick={() => setAsking(false)}>
              {HIDDEN_COPY.keep}
            </Button>
            <Button
              size="sm"
              disabled={!reason}
              busy={busy}
              onClick={() => reason && run(() => actions.show(detail.id, reason))}
            >
              {HIDDEN_COPY.show}
            </Button>
          </div>
          {failed ? (
            <p className="fmsg err" role="alert">
              {failed}
            </p>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}
