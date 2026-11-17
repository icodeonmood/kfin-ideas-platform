"use client";

import { useRef, type KeyboardEvent, type ReactNode } from "react";

import { IconTick } from "@/components/shell/icons";

export type ChipOption = { value: string; label: ReactNode; count?: number; disabled?: boolean };

const chipsClass = (scroll?: boolean, filter?: boolean) =>
  ["chips", scroll ? "scroll" : "", filter ? "filter" : ""].filter(Boolean).join(" ");

/**
 * C-CHIP, single choice ("Pick one"): a radio group of chips. Arrow keys move and select, Space selects, one tab stop
 * (the selected chip, or the first). Selected is a blue ring and wash with a leading tick, never colour alone. Filter
 * chips are the same with an "All" option first and live counts (C-CHIP.behaviour/3); pass `filter` and the tick shows
 * only on a phone (C-CHIP.states: "a leading tick on choice chips (sorting, filters on phone)").
 */
export function ChoiceChips({
  label,
  options,
  value,
  onChange,
  scroll,
  filter,
}: {
  /** The group's name, said by a screen reader ("Area"); a visible heading can point at the group instead. */
  label: string;
  options: ChipOption[];
  value: string | null;
  onChange: (value: string) => void;
  /** On a phone, scroll the row sideways instead of wrapping (F-SPACE.scroll/4). */
  scroll?: boolean;
  /** A filter row: the selected chip keeps its ring and wash, and takes the tick only at 640px and narrower. */
  filter?: boolean;
}) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const enabled = options.map((o, i) => (o.disabled ? -1 : i)).filter((i) => i >= 0);
  const current = options.findIndex((o) => o.value === value);
  const focusable = current >= 0 ? current : (enabled[0] ?? 0);

  const move = (from: number, step: number) => {
    const at = enabled.indexOf(from);
    const next = enabled[(at + step + enabled.length) % enabled.length];
    if (next === undefined) return;
    onChange(options[next]!.value);
    refs.current[next]?.focus();
  };

  const onKey = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      move(i, 1);
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      move(i, -1);
    }
  };

  return (
    <div className={chipsClass(scroll, filter)} role="radiogroup" aria-label={label}>
      {options.map((o, i) => (
        <button
          key={o.value}
          ref={(el) => {
            refs.current[i] = el;
          }}
          type="button"
          role="radio"
          className="chip"
          aria-checked={o.value === value}
          aria-disabled={o.disabled ? true : undefined}
          tabIndex={i === focusable ? 0 : -1}
          onClick={() => !o.disabled && onChange(o.value)}
          onKeyDown={(e) => onKey(e, i)}
        >
          <span className="chip-tick" aria-hidden="true">
            <IconTick size={14} />
          </span>
          {o.label}
          {o.count !== undefined ? <span className="chip-n num">{o.count}</span> : null}
        </button>
      ))}
    </div>
  );
}

/**
 * C-CHIP, multi choice ("Pick all that apply"): pressed buttons, any number including none. Each chip is its own tab
 * stop, as buttons are.
 */
export function MultiChips({
  label,
  options,
  values,
  onChange,
  scroll,
  filter,
}: {
  label: string;
  options: ChipOption[];
  values: string[];
  onChange: (values: string[]) => void;
  scroll?: boolean;
  /** As on ChoiceChips: the tick only on a phone. */
  filter?: boolean;
}) {
  const on = new Set(values);
  return (
    <div className={chipsClass(scroll, filter)} role="group" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          className="chip"
          aria-pressed={on.has(o.value)}
          aria-disabled={o.disabled ? true : undefined}
          onClick={() => {
            if (o.disabled) return;
            const next = new Set(on);
            if (next.has(o.value)) next.delete(o.value);
            else next.add(o.value);
            onChange(options.map((x) => x.value).filter((v) => next.has(v)));
          }}
        >
          <span className="chip-tick" aria-hidden="true">
            <IconTick size={14} />
          </span>
          {o.label}
          {o.count !== undefined ? <span className="chip-n num">{o.count}</span> : null}
        </button>
      ))}
    </div>
  );
}
