"use client";

import { useId } from "react";

/**
 * C-SORTS: "Sort by" and two to four options as small pressed buttons; exactly one is on. On a phone it is one text
 * button, "Sorted by <option>", that cycles through the options and says the change (C-SORTS.behaviour/5). The
 * screen keeps the sort in the URL so Back restores it.
 */
export function Sorts({
  options,
  value,
  onChange,
}: {
  options: Array<{ value: string; label: string }>;
  value: string;
  onChange: (value: string) => void;
}) {
  const labelId = useId();
  const at = Math.max(
    0,
    options.findIndex((o) => o.value === value),
  );
  const current = options[at];
  const next = options[(at + 1) % options.length];
  return (
    <>
      <div className="sorts sorts-wide" role="group" aria-labelledby={labelId}>
        <span id={labelId} className="sorts-l">
          Sort by
        </span>
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            aria-pressed={o.value === value}
            onClick={() => onChange(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
      <button
        type="button"
        className="tb sorts-cycle sorts-phone"
        onClick={() => next && onChange(next.value)}
        aria-describedby={`${labelId}-now`}
      >
        Sorted by {current?.label.toLowerCase()}
      </button>
      <span id={`${labelId}-now`} className="vh" aria-live="polite">
        {current ? `Sorted by ${current.label.toLowerCase()}` : ""}
      </span>
    </>
  );
}
