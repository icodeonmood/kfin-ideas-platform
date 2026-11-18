"use client";

/**
 * The frame every part of Check it sits in (S-05.layout/2): the counter, the question as the heading, one line, the
 * content, and the foot row with "Back" at the left and the forward button at the right. Then parts 1, 2, 6 and 7:
 * your words with the hidden details (C-HIDDEN), the sorting (L-SORT.fields), who would help, and the last look
 * with the declaration and Submit (L-SUBMIT.pre, L-SUBMIT.send). Parts 3 to 5 are in similar.tsx, proof.tsx, fix.tsx.
 */
import Link from "next/link";
import { forwardRef, useId, useState, type ReactNode } from "react";

import { IconTick } from "@/components/shell/icons";
import { Button, buttonClass } from "@/components/ui/button";
import { ChoiceChips, MultiChips } from "@/components/ui/chips";
import { FieldMsg } from "@/components/ui/field";
import type { Brings, ConfigResponse, FileItem, SendViewResponse, SortingResponse } from "@/lib/contracts";

import { CHECK_COPY, type PartNo } from "./copy";

const C = CHECK_COPY;

export const PartFrame = forwardRef<
  HTMLHeadingElement,
  {
    n: PartNo;
    heading: ReactNode;
    line?: ReactNode;
    phone?: boolean;
    children?: ReactNode;
    foot?: ReactNode;
    id?: string;
    /** The heading's own id, for the phone's count links (#pr-sort-h, #pr-sim-h). */
    headingId?: string;
    /** Where the part stands in the order shown, when it is not its own number (flag S2 "Check first"). */
    place?: number;
  }
>(function PartFrame({ n, heading, line, phone, children, foot, id, headingId, place }, ref) {
  const made = useId();
  const hid = headingId ?? made;
  return (
    <section className="ck-part" aria-labelledby={hid} id={id} data-part={n}>
      {phone ? null : <p className="ck-count meta">{n === 7 ? C.sendCounter : C.counter(place ?? n)}</p>}
      {phone ? (
        <h2 id={hid} ref={ref} tabIndex={-1} className="h2 ck-h">
          {heading}
        </h2>
      ) : (
        <h1 id={hid} ref={ref} tabIndex={-1} className="h1 ck-h">
          {heading}
        </h1>
      )}
      {line ? <p className="ck-line">{line}</p> : null}
      <div className="ck-body">{children}</div>
      {foot ? <div className="ck-foot">{foot}</div> : null}
    </section>
  );
});

// ---------------------------------------------------------------------------------------------------------------
// Part 1: your words
// ---------------------------------------------------------------------------------------------------------------

type WordKey = "title" | "summary" | "often";

export function WordsBody({
  values,
  attached,
  onSave,
  errors = {},
  onAttached,
  hidden,
  phone = false,
}: {
  values: Record<WordKey, string>;
  attached: FileItem[];
  onSave(key: WordKey, value: string): Promise<boolean>;
  /** Submit's `not_ready` for a line (field `title` or `summary`), in the server's words, shown under that line. */
  errors?: Partial<Record<WordKey, string>>;
  onAttached(): void;
  hidden: ReactNode;
  /** The phone boards' look (PhoneReview.md, PhoneEdit.md): each line labelled, the title too, with a "Change"
   * button ("Change title") in place of the pen. */
  phone?: boolean;
}) {
  return (
    <div className="ck-words">
      <EditLine
        k="title"
        label={C.words.title}
        value={values.title}
        onSave={onSave}
        serverError={errors.title}
        title
        phone={phone}
      />
      <EditLine
        k="summary"
        label={C.words.summary}
        value={values.summary}
        onSave={onSave}
        serverError={errors.summary}
        phone={phone}
      />
      <EditLine k="often" label={C.words.often} value={values.often} onSave={onSave} phone={phone} />
      {hidden}
      {attached.length ? (
        <div className="ck-att">
          <p className="lbl">
            {C.words.attached} <span className="meta">{C.words.attachedCount(attached.length)}</span>
          </p>
          <ul className="ck-att-l">
            {attached.map((f) => (
              <li key={f.id}>
                <span
                  className={`fbadge fb-${(f.name.split(".").pop() ?? "").toLowerCase()}`}
                  aria-hidden="true"
                >
                  {(f.name.split(".").pop() ?? "").toUpperCase()}
                </span>
                <span>{f.name}</span>
              </li>
            ))}
          </ul>
          <Button variant="text-blue" onClick={onAttached}>
            {C.words.changeAttached}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function EditLine({
  k,
  label,
  value,
  onSave,
  serverError,
  title,
  phone = false,
}: {
  k: WordKey;
  label: string;
  value: string;
  onSave(key: WordKey, value: string): Promise<boolean>;
  serverError?: string;
  title?: boolean;
  phone?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value);
  const [localError, setError] = useState<string | null>(null);
  const error = localError ?? serverError ?? null;
  const [busy, setBusy] = useState(false);
  const id = useId();

  const save = async () => {
    const v = text.trim();
    if (k === "title" && (v.length < 1 || v.length > 70)) return setError(C.words.titleNeeded);
    if (k === "summary" && !v) return setError(C.words.summaryNeeded);
    if (v === value.trim()) {
      setEditing(false);
      setError(null);
      return;
    }
    setBusy(true);
    const ok = await onSave(k, v);
    setBusy(false);
    if (ok) {
      setEditing(false);
      setError(null);
    } else setError(C.failed);
  };

  return (
    <div className={title ? "ck-w ck-w-title" : "ck-w"}>
      {title && !phone ? null : (
        <p className="lbl" id={`${id}-l`}>
          {label}
        </p>
      )}
      {editing ? (
        <div className="ck-w-edit">
          {k === "summary" ? (
            <textarea
              className="fld textarea"
              aria-label={label}
              rows={4}
              autoFocus
              value={text}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? `${id}-m` : undefined}
              onChange={(e) => setText(e.target.value)}
              onBlur={() => void save()}
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  setText(value);
                  setEditing(false);
                  setError(null);
                }
              }}
            />
          ) : (
            <input
              className="fld"
              aria-label={label}
              autoFocus
              value={text}
              maxLength={k === "title" ? 70 : 200}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? `${id}-m` : undefined}
              onChange={(e) => setText(e.target.value)}
              onBlur={() => void save()}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void save();
                } else if (e.key === "Escape") {
                  setText(value);
                  setEditing(false);
                  setError(null);
                }
              }}
            />
          )}
          {busy ? <span className="spin" aria-hidden="true" /> : null}
        </div>
      ) : (
        <div className="ck-w-v">
          {title ? <h3 className="h3 ck-title">{value}</h3> : <p className="ck-v">{value}</p>}
          {phone ? (
            <button
              type="button"
              className="tb blue ck-chg"
              aria-describedby={error ? `${id}-m` : undefined}
              onClick={() => {
                setText(value);
                setEditing(true);
              }}
            >
              {C.words.changePhone}
              <span className="vh"> {C.words.changeWhat[k]}</span>
            </button>
          ) : (
            <button
              type="button"
              className="ck-pen"
              aria-label={C.words.change[k]}
              aria-describedby={error ? `${id}-m` : undefined}
              onClick={() => {
                setText(value);
                setEditing(true);
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path
                  d="M4 20h4L19 9l-4-4L4 16v4Zm11-15 4 4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          )}
        </div>
      )}
      {error ? <FieldMsg id={`${id}-m`}>{error}</FieldMsg> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------------------------
// Part 2: sorting (L-SORT.fields)
// ---------------------------------------------------------------------------------------------------------------

type Controls = NonNullable<ConfigResponse["sorting"]["controls"]>;

export function SortingBody({
  sorting,
  controls,
  onChange,
  unconfirmedTried,
  error,
}: {
  sorting: SortingResponse;
  controls: Controls;
  onChange(patch: { affects?: string[]; kind?: string; area?: string; brings?: Brings[] }): void;
  unconfirmedTried: boolean;
  error: string | null;
}) {
  const affects = sorting.affects.value ?? [];
  const area = sorting.area.value;
  // Values picked from the search join the chips shown (C-CHIP), in the order the lists give them.
  const affectsShown = [
    ...controls.affects.shown,
    ...affects.filter((a) => !controls.affects.shown.includes(a)),
  ];
  const areasShown = [...controls.area.shown, ...(area && !controls.area.shown.includes(area) ? [area] : [])];
  const exclusive = controls.brings.exclusive;
  return (
    <div className={unconfirmedTried && !sorting.confirmed ? "ck-sort tile bad" : "ck-sort tile"}>
      <div className="ck-sort-g">
        <SortField label={C.sorting.affects} rule={controls.affects.rule} why={sorting.affects.why_line}>
          <MultiChips
            label={C.sorting.affects}
            options={affectsShown.map((v) => ({ value: v, label: v }))}
            values={affects}
            onChange={(v) => onChange({ affects: v })}
          />
          <SearchAdd
            label={controls.affects.search_label}
            hint={controls.affects.search_link}
            all={controls.affects.all.filter((v) => !affectsShown.includes(v))}
            onPick={(v) => onChange({ affects: [...affects, v] })}
          />
        </SortField>
        <SortField label={C.sorting.kind} rule={controls.kind.rule} why={sorting.kind.why_line}>
          <ChoiceChips
            label={C.sorting.kind}
            options={controls.kind.options.map((o) => ({ value: o.value, label: o.label }))}
            value={sorting.kind.value}
            onChange={(v) => onChange({ kind: v })}
          />
        </SortField>
        <SortField label={C.sorting.area} rule={controls.area.rule} why={sorting.area.why_line}>
          <ChoiceChips
            label={C.sorting.area}
            options={areasShown.map((v) => ({ value: v, label: v }))}
            value={area}
            onChange={(v) => onChange({ area: v })}
          />
          <SearchAdd
            label={controls.area.search_label}
            hint={controls.area.search_link}
            all={controls.area.all.filter((v) => !areasShown.includes(v))}
            onPick={(v) => onChange({ area: v })}
          />
        </SortField>
        <SortField label={C.sorting.brings} rule={controls.brings.rule} why={sorting.brings.why_line}>
          <MultiChips
            label={C.sorting.brings}
            options={controls.brings.options.map((o) => ({ value: o.value, label: o.label }))}
            values={sorting.brings.value ?? []}
            onChange={(v) =>
              onChange({ brings: withExclusive(sorting.brings.value ?? [], v as Brings[], exclusive) })
            }
          />
        </SortField>
      </div>
      {sorting.note ? (
        <p className={sorting.confirmed ? "ck-cstate ok" : "ck-cstate"} role="status">
          {sorting.confirmed ? <IconTick size={14} /> : null}
          {sorting.note}
        </p>
      ) : null}
      {unconfirmedTried && !sorting.confirmed ? <FieldMsg>{C.sorting.unconfirmed}</FieldMsg> : null}
      {error ? <FieldMsg>{error}</FieldMsg> : null}
    </div>
  );
}

/** "Not sure yet" counts and clears the others; any other choice clears it (V-FIELDS.checkit/3). */
export function withExclusive(before: Brings[], after: Brings[], exclusive: Brings): Brings[] {
  const had = new Set(before);
  const added = after.filter((x) => !had.has(x));
  if (added.includes(exclusive)) return [exclusive];
  if (added.length) return after.filter((x) => x !== exclusive);
  return after;
}

function SortField({
  label,
  rule,
  why,
  children,
}: {
  label: string;
  rule: string;
  why: string | null;
  children: ReactNode;
}) {
  return (
    <div className="ck-sf">
      <div className="ck-sf-h">
        <p className="ck-sf-l">{label}</p>
        <p className="meta">{rule}</p>
      </div>
      {children}
      {why ? <p className="ck-why">{why}</p> : null}
    </div>
  );
}

/** "Someone else? Search all 6": a small combobox over the rest of the list (L-SORT.fields, C-CHIP). */
function SearchAdd({
  label,
  hint,
  all,
  onPick,
}: {
  label: string;
  hint: string;
  all: string[];
  onPick(value: string): void;
}) {
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const id = useId();
  const found = all.filter((v) => v.toLowerCase().includes(text.trim().toLowerCase()));
  const pick = (v: string) => {
    onPick(v);
    setText("");
    setOpen(false);
  };
  if (!all.length) return null;
  return (
    <div className="cbx">
      <span className="vh">{hint}</span>
      <input
        className="cin"
        type="text"
        role="combobox"
        aria-label={label}
        placeholder={label}
        aria-expanded={open && found.length > 0}
        aria-controls={open && found.length ? `${id}-lb` : undefined}
        aria-autocomplete="list"
        aria-activedescendant={open && found[active] ? `${id}-o${active}` : undefined}
        autoComplete="off"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setOpen(true);
            setActive((a) => Math.min(a + 1, Math.max(found.length - 1, 0)));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(a - 1, 0));
          } else if (e.key === "Enter" && open && found[active]) {
            e.preventDefault();
            pick(found[active]!);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {open && found.length ? (
        <ul className="lb" role="listbox" id={`${id}-lb`} aria-label={label}>
          {found.map((v, i) => (
            <li
              key={v}
              id={`${id}-o${i}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? "act" : undefined}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(v);
              }}
            >
              {v}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------------------------
// Part 6: who would help
// ---------------------------------------------------------------------------------------------------------------

export const HELPERS_MAX = 140;

export function HelpersBody({
  options,
  picks,
  text,
  onPicks,
  onText,
  error,
}: {
  options: string[];
  picks: string[];
  text: string;
  onPicks(picks: string[]): void;
  onText(text: string): void;
  error: string | null;
}) {
  const id = useId();
  return (
    <div className="ck-helpers">
      <MultiChips
        label={C.helpers.picks}
        options={options.map((o) => ({ value: o, label: o }))}
        values={picks}
        onChange={onPicks}
      />
      <div className="ck-q">
        <p className="lbl" id={`${id}-l`}>
          {C.helpers.own}
        </p>
        <span className="vh" id={`${id}-p`}>
          {C.helpers.ownPlaceholder}
        </span>
        <input
          className="fld"
          type="text"
          maxLength={HELPERS_MAX}
          placeholder={C.helpers.ownPlaceholder}
          aria-labelledby={`${id}-l ${id}-p`}
          aria-describedby={`${id}-c`}
          value={text}
          onChange={(e) => onText(e.target.value)}
        />
        <p className="help num" id={`${id}-c`}>
          {C.helpers.counter(text.length, HELPERS_MAX)}
        </p>
      </div>
      {error ? <FieldMsg>{error}</FieldMsg> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------------------------
// Part 7: send it (L-SUBMIT.pre, L-SUBMIT.send)
// ---------------------------------------------------------------------------------------------------------------

export type SendState =
  | { kind: "idle" }
  | { kind: "sending" }
  /** The server's line when it sent one: not confirmed, or confirmed with a field left empty. */
  | { kind: "unconfirmed"; message?: string }
  | { kind: "failed" }
  /** `final`: nothing more to send from here (`not_a_draft`), so Submit stays unavailable. */
  | { kind: "refused"; message: string; final?: boolean }
  | { kind: "queued" };

export function SendRows({ view, onChange }: { view: SendViewResponse; onChange(step: string): void }) {
  return (
    <dl className="ck-rows">
      {view.rows.map((r) => (
        <div className="ck-row" key={r.key}>
          <dt>
            <span className={r.ok ? "ck-mark ok" : "ck-mark warn"} aria-hidden="true">
              {r.ok ? <IconTick size={12} /> : "!"}
            </span>
            {r.label}
          </dt>
          <dd>
            {r.key === "title" ? (
              <p className="ck-v ck-v-title">{r.value}</p>
            ) : (
              <p className="ck-v">{r.value}</p>
            )}
            <Button
              variant="text-blue"
              aria-label={C.send.changeOf(r.label)}
              onClick={() => onChange(r.step)}
            >
              {C.send.change}
            </Button>
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function SendBar({
  declaration,
  button,
  state,
  offline,
  blockedLine,
  canSubmit,
  onSubmit,
  onGoToSorting,
  back,
}: {
  declaration: string;
  button: string;
  state: SendState;
  offline: boolean;
  /** Why Submit is unavailable (a merge request waiting): shown above the button. */
  blockedLine: string | null;
  canSubmit: boolean;
  onSubmit(): void;
  onGoToSorting(): void;
  back: ReactNode;
}) {
  // One Submit button stays on the page through every state ("Try again" after a failed send), so focus never drops
  // to the page when the words around it change; each message is announced where it appears (WCAG 2.4.3, 4.1.3).
  const final = state.kind === "refused" && state.final === true;
  return (
    <div className="ck-send">
      <p className="decl">{declaration}</p>
      {state.kind === "unconfirmed" ? (
        <div className="bmsg bad" role="alert">
          <span>{state.message || C.send.unconfirmed}</span>
          <Button variant="text" onClick={onGoToSorting}>
            {C.send.goToSorting}
          </Button>
        </div>
      ) : null}
      {state.kind === "refused" ? (
        <div className="bmsg bad" role="alert">
          <span>{state.message}</span>
        </div>
      ) : null}
      {offline || state.kind === "queued" ? (
        <p className="bmsg warn" role="status">
          {C.send.offline}
        </p>
      ) : null}
      {state.kind === "failed" ? (
        <p className="bmsg bad" role="alert">
          {C.send.sendFailed}
        </p>
      ) : null}
      {blockedLine && !canSubmit ? <p className="bmsg info">{blockedLine}</p> : null}
      <div className="ck-foot">
        {back}
        <Button
          disabled={!canSubmit || final}
          busy={state.kind === "sending"}
          busyLabel={C.send.sending}
          onClick={onSubmit}
        >
          {state.kind === "failed" ? C.retry : button}
        </Button>
      </div>
    </div>
  );
}

/** "Back to your words": a link to Tell it (S-04B), drawn as a text button. */
export function BackToWords({ href }: { href: string }) {
  return (
    <Link href={href} className={buttonClass("text")}>
      {C.words.backToWords}
    </Link>
  );
}
