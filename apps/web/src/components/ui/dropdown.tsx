"use client";

import { useEffect, useId, useRef, useState } from "react";

export type DropdownOption = { value: string; title: string; meta?: string };

/**
 * C-DROPDOWN: a field-looking button over a list of tick boxes, for picking any number of the person's own items.
 * Nothing is picked at first ("None picked"); one picked shows its title, several "2 ideas picked". The list stays open
 * while ticking; Escape closes the list only, not the sheet around it (C-DROPDOWN/5).
 */
export function Dropdown({
  label,
  options,
  values,
  onChange,
  noun,
}: {
  label: string;
  options: DropdownOption[];
  values: string[];
  onChange: (values: string[]) => void;
  /** For the summary: { one: "idea", many: "ideas" } gives "2 ideas picked". */
  noun: { one: string; many: string };
}) {
  const [open, setOpen] = useState(false);
  const labelId = useId();
  const listId = useId();
  const button = useRef<HTMLButtonElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const picked = options.filter((o) => values.includes(o.value));
  const summary =
    picked.length === 0
      ? "None picked"
      : picked.length === 1
        ? picked[0]!.title
        : `${picked.length} ${noun.many} picked`;

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, [open]);

  return (
    <div
      className="dd"
      ref={wrap}
      onKeyDown={(e) => {
        if (e.key === "Escape" && open) {
          e.stopPropagation();
          setOpen(false);
          button.current?.focus();
        }
      }}
    >
      <p id={labelId} className="lbl">
        {label}
      </p>
      <button
        ref={button}
        type="button"
        className="dd-b fld"
        aria-labelledby={`${labelId} ${listId}-v`}
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((o) => !o)}
      >
        <span id={`${listId}-v`} className={picked.length ? "dd-v" : "dd-v none"}>
          {summary}
        </span>
        <svg
          className="dd-c"
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      <div id={listId} className="dd-l" role="group" aria-labelledby={labelId} hidden={!open}>
        {options.map((o) => (
          <label key={o.value} className="dd-o">
            <input
              type="checkbox"
              checked={values.includes(o.value)}
              onChange={(e) =>
                onChange(
                  e.target.checked
                    ? options.map((x) => x.value).filter((v) => v === o.value || values.includes(v))
                    : values.filter((v) => v !== o.value),
                )
              }
            />
            <span className="dd-ot">
              <span className="dd-t">{o.title}</span>
              {o.meta ? <span className="dd-m">{o.meta}</span> : null}
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}
