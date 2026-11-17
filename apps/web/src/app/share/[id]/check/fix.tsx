"use client";

/**
 * Part 5, "Got an idea how to solve it?", and the fix sheet (S-05.fix). The part shows "Add your fix", a started fix
 * ("You started a fix. It isn't included yet." + "Carry on with your fix"), or the added fix: "Included, 5 of 5
 * ready", the one-line fix, its size line, "Change" and "Remove".
 *
 * The sheet is a right-hand dialog (full screen on a phone), mounted at the page root: six questions, a readiness
 * line that counts what is filled, and the most useful next answer. Only "How would you solve it?" is needed. The
 * cross is "Close, and keep what you wrote" (a started fix, `included: false`), saved before the sheet closes;
 * "Cancel" and Escape close without saving (S-05.fix OPEN, P-DECISIONS.open/13, BLD-C134). While it is open the page
 * behind it is inert, so neither a pointer nor a screen reader reaches it. Amounts go to the server as typed and come
 * back normalised (L-WORTH/1).
 */
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui/button";
import { ChoiceChips, MultiChips } from "@/components/ui/chips";
import { FieldMsg } from "@/components/ui/field";
import { BASIS_LABEL, type Basis, type FixRequest } from "@/lib/contracts";

import { CHECK_COPY } from "./copy";
import { fixNext, fixReady, type FixForm } from "./model";

const C = CHECK_COPY.fix;
const S = CHECK_COPY.sheet;

/** What part 5 shows. */
export type FixPart =
  | { kind: "none" }
  | { kind: "started" }
  | { kind: "added"; line: string; fixLine: string; sizeLine?: string };

export function FixPartBody({
  part,
  onOpen,
  onRemove,
  removing,
  error,
  words,
}: {
  part: FixPart;
  onOpen(): void;
  onRemove(): void;
  removing: boolean;
  error: string | null;
  /** The edit page's row (S-06B; Edit.md): "Got an idea how to solve it?" and its line, under its own "Your fix"
   * heading, so the row's title is not a heading there. Check it leaves it out. */
  words?: { title: string; line: string };
}) {
  return (
    <div className="ck-fix">
      {part.kind === "added" ? (
        <div className="fixrow tile">
          <div>
            <p className="ck-fix-ok">{part.line}</p>
            <p className="ck-fix-l">{part.fixLine}</p>
            {part.sizeLine ? <p className="meta">{part.sizeLine}</p> : null}
          </div>
          <div className="fxa">
            <Button variant="text-blue" aria-haspopup="dialog" aria-label={C.changeLabel} onClick={onOpen}>
              {C.change}
            </Button>
            <Button variant="text" aria-label={C.removeLabel} busy={removing} onClick={onRemove}>
              {C.remove}
            </Button>
          </div>
        </div>
      ) : (
        <div className="fixrow tile">
          <div>
            {words ? <p className="h3">{words.title}</p> : <h2 className="h3">{C.rowTitle}</h2>}
            <p className="meta">{words ? words.line : C.rowLine}</p>
            {part.kind === "started" ? <p className="ck-started">{C.started}</p> : null}
          </div>
          <div className="fxa">
            <Button variant="line" size="sm" aria-haspopup="dialog" onClick={onOpen}>
              {part.kind === "started" ? C.carryOn : C.add}
            </Button>
          </div>
        </div>
      )}
      {error ? <FieldMsg>{error}</FieldMsg> : null}
    </div>
  );
}

/** What stops the sheet: a line under "How would you solve it?", under the figures, or at the foot. */
export type FixProblem = { field: "how" | "worth" | null; message: string };

const BASES = (Object.keys(BASIS_LABEL) as Basis[]).map((b) => ({ value: b, label: BASIS_LABEL[b] }));
const MEASURES: Array<{ value: FixForm["measures"][number]; label: string }> = [
  { value: "hours", label: S.hours },
  { value: "cost", label: S.cost },
  { value: "revenue", label: S.revenue },
  { value: "tools", label: S.tools },
];

export function FixSheet({
  open,
  initial,
  onCancel,
  onKeep,
  onAdd,
}: {
  open: boolean;
  initial: FixForm;
  onCancel(): void;
  /** The cross: keep what was typed as a started fix (or close if nothing was); resolves to what stopped it. */
  onKeep(form: FixForm): Promise<FixProblem | null>;
  /** "Add my fix": resolves to a field error to show, or null when added. */
  onAdd(form: FixForm): Promise<FixProblem | null>;
}) {
  if (!open || typeof document === "undefined") return null;
  return createPortal(
    <Sheet initial={initial} onCancel={onCancel} onKeep={onKeep} onAdd={onAdd} />,
    document.body,
  );
}

function Sheet({
  initial,
  onCancel,
  onKeep,
  onAdd,
}: {
  initial: FixForm;
  onCancel(): void;
  onKeep(form: FixForm): Promise<FixProblem | null>;
  onAdd(form: FixForm): Promise<FixProblem | null>;
}) {
  const [f, setF] = useState<FixForm>(initial);
  const [error, setError] = useState<FixProblem | null>(null);
  const [busy, setBusy] = useState(false);
  const [keeping, setKeeping] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const opener = useRef<Element | null>(null);
  const how = useRef<HTMLTextAreaElement>(null);
  const ids = useId();
  const set = <K extends keyof FixForm>(k: K, v: FixForm[K]) => setF((x) => ({ ...x, [k]: v }));

  useEffect(() => {
    opener.current = document.activeElement;
    title.current?.focus();
    // The page behind is inert while the sheet is open (WCAG 2.4.3, 1.3.2): every other child of <body>.
    const others = Array.from(document.body.children).filter(
      (el): el is HTMLElement =>
        el instanceof HTMLElement && el !== wrap.current && !el.hasAttribute("inert"),
    );
    for (const el of others) el.setAttribute("inert", "");
    return () => {
      for (const el of others) el.removeAttribute("inert");
      const o = opener.current;
      if (o instanceof HTMLElement && o.isConnected) o.focus();
    };
  }, []);

  /** The cross: saved, then closed; if the save is refused the sheet stays open and says why. */
  const keep = async () => {
    if (keeping) return;
    setKeeping(true);
    const problem = await onKeep(f);
    setKeeping(false);
    if (problem) setError(problem);
  };

  const ready = fixReady(f);
  const next = fixNext(f);

  const add = async () => {
    if (!f.how.trim()) {
      setError({ field: "how", message: S.howNeeded });
      how.current?.focus();
      return;
    }
    setBusy(true);
    const problem = await onAdd(f);
    setBusy(false);
    setError(problem);
    if (problem?.field === "how") how.current?.focus();
  };

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      // Escape is Cancel: it never saves without the person asking (only the cross keeps what was written).
      e.preventDefault();
      onCancel();
      return;
    }
    if (e.key !== "Tab" || !box.current) return;
    const items = Array.from(
      box.current.querySelectorAll<HTMLElement>(
        'button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((el) => !el.hasAttribute("disabled") && el.offsetParent !== null);
    if (!items.length) return;
    const first = items[0]!;
    const last = items[items.length - 1]!;
    if (e.shiftKey && (document.activeElement === first || document.activeElement === title.current)) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  const figure = (key: "hours" | "cost" | "revenue", unit: string, placeholder: string) => (
    <div className="ck-fig">
      <label className="vh" htmlFor={`${ids}-${key}`}>
        {MEASURES.find((m) => m.value === key)!.label}, {unit}
      </label>
      <input
        id={`${ids}-${key}`}
        className="fld"
        type="text"
        inputMode="decimal"
        placeholder={placeholder}
        value={f[key]}
        aria-describedby={`${ids}-${key}-u${error?.field === "worth" ? ` ${ids}-worth-m` : ""}`}
        aria-invalid={error?.field === "worth" ? true : undefined}
        onChange={(e) => set(key, e.target.value)}
      />
      <span className="meta" id={`${ids}-${key}-u`}>
        {unit}
      </span>
    </div>
  );

  return (
    <div className="ck-sheet-wrap" ref={wrap}>
      <div className="ck-sheet-scrim" aria-hidden="true" />
      <div
        ref={box}
        className="ck-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${ids}-t`}
        onKeyDown={onKey}
      >
        <div className="ck-sheet-h">
          <h2 id={`${ids}-t`} ref={title} tabIndex={-1} className="h2">
            {S.title}
          </h2>
          <button
            type="button"
            className="ck-x"
            aria-label={S.close}
            aria-busy={keeping ? true : undefined}
            onClick={() => void keep()}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="ck-sheet-b">
          <p className="meta">{S.intro}</p>
          <div className="ck-ready" role="status">
            <p className="ck-ready-n">{S.readiness(ready)}</p>
            {next ? <p className="meta">{S.next[next]}</p> : null}
          </div>

          <div className="ck-q">
            <label className="lbl" htmlFor={`${ids}-how`}>
              {S.how}
            </label>
            <textarea
              ref={how}
              id={`${ids}-how`}
              className="fld textarea"
              rows={3}
              value={f.how}
              aria-invalid={error?.field === "how" ? true : undefined}
              aria-describedby={`${ids}-how-h${error?.field === "how" ? ` ${ids}-how-m` : ""}`}
              onChange={(e) => set("how", e.target.value)}
            />
            <p className="help" id={`${ids}-how-h`}>
              {S.howHelp}
            </p>
            {error?.field === "how" ? <FieldMsg id={`${ids}-how-m`}>{error.message}</FieldMsg> : null}
          </div>

          <div className="ck-q">
            <label className="lbl" htmlFor={`${ids}-needs`}>
              {S.needs} <span className="opt">{S.optional}</span>
            </label>
            <textarea
              id={`${ids}-needs`}
              className="fld textarea"
              rows={2}
              value={f.needs}
              aria-describedby={`${ids}-needs-h`}
              onChange={(e) => set("needs", e.target.value)}
            />
            <p className="help" id={`${ids}-needs-h`}>
              {S.needsHelp}
            </p>
          </div>

          <div className="ck-q">
            <p className="lbl" id={`${ids}-solved`}>
              {S.solved}
            </p>
            <ChoiceChips
              label={S.solved}
              options={S.solvedOptions.map((o) => ({ value: o.value, label: o.label }))}
              value={f.solved}
              onChange={(v) => set("solved", v)}
            />
          </div>

          <div className="ck-q">
            <p className="lbl">{S.worth}</p>
            <p className="help">{S.worthHelp}</p>
            <MultiChips
              label={S.worth}
              options={MEASURES}
              values={f.measures}
              onChange={(v) => set("measures", v as FixForm["measures"])}
            />
            <div className="ck-figs">
              {f.measures.includes("hours") ? figure("hours", S.hoursUnit, S.hoursPlaceholder) : null}
              {f.measures.includes("cost") ? figure("cost", S.money, S.moneyPlaceholder) : null}
              {f.measures.includes("revenue") ? figure("revenue", S.money, S.moneyPlaceholder) : null}
            </div>
            {error?.field === "worth" ? <FieldMsg id={`${ids}-worth-m`}>{error.message}</FieldMsg> : null}
          </div>

          <div className="ck-q">
            <p className="lbl">{S.basis}</p>
            <ChoiceChips label={S.basis} options={BASES} value={f.basis} onChange={(v) => set("basis", v)} />
          </div>

          <div className="ck-q">
            <label className="lbl" htmlFor={`${ids}-risks`}>
              {S.risks} <span className="opt">{S.optional}</span>
            </label>
            <textarea
              id={`${ids}-risks`}
              className="fld textarea"
              rows={2}
              value={f.risks}
              aria-describedby={`${ids}-risks-h`}
              onChange={(e) => set("risks", e.target.value)}
            />
            <p className="help" id={`${ids}-risks-h`}>
              {S.risksHelp}
            </p>
          </div>
          {error && error.field === null ? <FieldMsg>{error.message}</FieldMsg> : null}
        </div>
        <div className="ck-sheet-f">
          <Button variant="text" onClick={onCancel}>
            {S.cancel}
          </Button>
          <Button busy={busy} onClick={() => void add()}>
            {S.submit}
          </Button>
        </div>
      </div>
    </div>
  );
}

/** Whether the person typed anything at all in the sheet. */
export function typedAnything(f: FixForm): boolean {
  return Boolean(
    f.how.trim() ||
    f.needs.trim() ||
    f.solved ||
    f.measures.length ||
    f.basis ||
    f.risks.trim() ||
    f.hours.trim() ||
    f.cost.trim() ||
    f.revenue.trim(),
  );
}

export type { FixRequest };
