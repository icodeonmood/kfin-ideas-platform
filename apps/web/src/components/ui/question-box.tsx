"use client";

import { useId, useState, type FormEvent } from "react";

/**
 * C-FIELD.kinds, the question box (S-R2.panel.ask): the reviewer asks in their own words, and each question is pinned
 * to a part of the idea, so the sharer answers it there. A text area with a "Pinned to" selector (a native select, so
 * it is a menu every screen reader knows) and a round add button inside the box. Enter adds; Shift+Enter is a new line.
 */
export function QuestionBox({
  label,
  parts,
  pinned,
  onPinned,
  onAdd,
  hint = "Enter adds your question. Shift and Enter for a new line.",
}: {
  /** "What would you like to ask Kavya?" with the sharer's first name. */
  label: string;
  parts: Array<{ value: string; label: string }>;
  pinned: string;
  onPinned: (part: string) => void;
  onAdd: (question: string, part: string) => void;
  /** The box says how Enter works (F-A11Y.rules/8), in the pattern of Tell it's own line. */
  hint?: string;
}) {
  const id = useId();
  const [text, setText] = useState("");
  const add = (e?: FormEvent) => {
    e?.preventDefault();
    const q = text.trim();
    if (!q) return;
    onAdd(q, pinned);
    setText("");
  };
  return (
    <form className="qbx" onSubmit={add}>
      <label htmlFor={`${id}-q`} className="lbl">
        {label}
      </label>
      <div className="qbx-box">
        <textarea
          id={`${id}-q`}
          className="qbx-t"
          rows={2}
          value={text}
          aria-describedby={`${id}-h`}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              add();
            }
          }}
        />
        <div className="qbx-row">
          <label className="qbx-pin">
            <span>Pinned to</span>
            <select value={pinned} onChange={(e) => onPinned(e.target.value)}>
              {parts.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            className="qbx-add"
            aria-label="Add this question"
            aria-disabled={text.trim() ? undefined : true}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>
        </div>
      </div>
      <p id={`${id}-h`} className="help">
        {hint}
      </p>
    </form>
  );
}
