"use client";

import { useId, useRef, type ClipboardEvent, type KeyboardEvent, type ReactNode } from "react";

import { FieldMsg } from "./field";

/**
 * C-FIELD.kinds, the 6-digit code (S-02, built behind the email-code switch, BLD-E002): six boxes on the numeric
 * keypad, one-time-code autofill, paste fills all six, typing moves on, Backspace steps back. A wrong code shakes the
 * boxes and says what to do under them. `onComplete` fires when a full code is in and differs from the one before, so a retry after a wrong code
 * signs in without clearing the boxes first.
 */
export function CodeField({
  label,
  value,
  onChange,
  onComplete,
  error,
  length = 6,
}: {
  /** Said for the group ("The 6-digit code from the email"). */
  label: ReactNode;
  value: string;
  onChange: (value: string) => void;
  onComplete?: (value: string) => void;
  error?: ReactNode;
  length?: number;
}) {
  const id = useId();
  const boxes = useRef<Array<HTMLInputElement | null>>([]);
  const digits = Array.from({ length }, (_, i) => value[i] ?? "");

  const set = (next: string) => {
    const clean = next.replace(/\D/g, "").slice(0, length);
    onChange(clean);
    if (clean.length === length && clean !== value) onComplete?.(clean);
    return clean;
  };

  const onInput = (i: number, raw: string) => {
    const d = raw.replace(/\D/g, "");
    if (!d) return;
    if (d.length > 1) {
      const clean = set(value.slice(0, i) + d);
      boxes.current[Math.min(clean.length, length - 1)]?.focus();
      return;
    }
    // A digit goes in the first empty box at or before this one, so the code never has a gap
    const at = Math.min(i, value.length);
    const chars = digits.slice();
    chars[at] = d;
    set(chars.join(""));
    boxes.current[Math.min(at + 1, length - 1)]?.focus();
  };

  const onKey = (i: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace") {
      e.preventDefault();
      const chars = digits.slice();
      if (chars[i]) {
        chars[i] = "";
        onChange(chars.join("").slice(0, i) + chars.slice(i + 1).join(""));
      } else if (i > 0) {
        chars[i - 1] = "";
        onChange(chars.slice(0, i - 1).join(""));
        boxes.current[i - 1]?.focus();
      }
    } else if (e.key === "ArrowLeft" && i > 0) {
      e.preventDefault();
      boxes.current[i - 1]?.focus();
    } else if (e.key === "ArrowRight" && i < length - 1) {
      e.preventDefault();
      boxes.current[i + 1]?.focus();
    }
  };

  const onPaste = (e: ClipboardEvent<HTMLInputElement>) => {
    const text = e.clipboardData.getData("text");
    if (!/\d/.test(text)) return;
    e.preventDefault();
    const clean = set(text);
    boxes.current[Math.min(clean.length, length - 1)]?.focus();
  };

  return (
    <div className="otp-wrap">
      <div className={error ? "otp bad" : "otp"} role="group" aria-labelledby={`${id}-l`}>
        <span id={`${id}-l`} className="vh">
          {label}
        </span>
        {digits.map((d, i) => (
          <input
            key={i}
            ref={(el) => {
              boxes.current[i] = el;
            }}
            className="otp-b"
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            autoComplete={i === 0 ? "one-time-code" : "off"}
            maxLength={i === 0 ? length : 1}
            value={d}
            aria-label={`Digit ${i + 1} of ${length}`}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? `${id}-msg` : undefined}
            onChange={(e) => onInput(i, e.target.value)}
            onKeyDown={(e) => onKey(i, e)}
            onPaste={onPaste}
            onFocus={(e) => e.currentTarget.select()}
          />
        ))}
      </div>
      {error ? <FieldMsg id={`${id}-msg`}>{error}</FieldMsg> : null}
    </div>
  );
}
