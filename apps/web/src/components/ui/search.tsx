"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { IconSearch } from "@/components/shell/icons";

export type SearchFilter = { value: string; label: string; count?: number };

/**
 * C-SEARCH, the bar (lane D; "ask in your own words" is lane F's, L-SEARCH): one glass bar with the search icon, the
 * active filters as removable chips, the input, Clear, and Filter. Focusing it opens the panel: "Narrow it to" with
 * live counts, and optionally the example questions. Backspace in an empty box removes the last chip; Enter runs
 * the search; Escape closes the panel and keeps the text. The screen keeps text and filters in the URL.
 */
export function SearchBar({
  label,
  placeholder,
  text,
  onText,
  filters,
  picked,
  onPicked,
  onSubmit,
  asks,
  onAsk,
  foot,
  answer,
}: {
  /** The input's name, said by a screen reader ("Search your ideas"). */
  label: string;
  placeholder: string;
  text: string;
  onText: (text: string) => void;
  filters: SearchFilter[];
  picked: string[];
  onPicked: (picked: string[]) => void;
  onSubmit: (text: string) => void;
  /** "Or ask in your own words": example questions (C-SEARCH.behaviour/1). */
  asks?: string[];
  onAsk?: (question: string) => void;
  /** The line under the panel saying what search reads. */
  foot?: ReactNode;
  /** The one-line result or answer (C-SEARCH.behaviour/3–4). */
  answer?: { line: ReactNode; source?: ReactNode };
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const inputId = useId();
  const wrap = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const byValue = new Map(filters.map((f) => [f.value, f]));

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, [open]);

  const onKey = (e: KeyboardEvent<HTMLElement>) => {
    if (e.key === "Escape" && open) {
      e.stopPropagation();
      setOpen(false);
      input.current?.focus();
    }
  };

  const toggle = (value: string) =>
    onPicked(picked.includes(value) ? picked.filter((v) => v !== value) : [...picked, value]);

  return (
    <div className="qwrap" ref={wrap} onKeyDown={onKey}>
      <form
        className="qbox"
        role="search"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          setOpen(false);
          onSubmit(text);
        }}
      >
        <IconSearch size={20} />
        {picked.map((v) => (
          <span key={v} className="qpill">
            {byValue.get(v)?.label ?? v}
            <button
              type="button"
              className="qx"
              aria-label={`Remove the filter: ${byValue.get(v)?.label ?? v}`}
              onClick={() => toggle(v)}
            >
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.6"
                strokeLinecap="round"
                aria-hidden="true"
              >
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          </span>
        ))}
        <label className="vh" htmlFor={inputId}>
          {label}
        </label>
        <input
          ref={input}
          id={inputId}
          type="search"
          autoComplete="off"
          placeholder={placeholder}
          value={text}
          onChange={(e) => onText(e.target.value)}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Backspace" && text === "" && picked.length) onPicked(picked.slice(0, -1));
          }}
        />
        {text || picked.length ? (
          <button
            type="button"
            className="qclr"
            onClick={() => {
              onText("");
              onPicked([]);
              input.current?.focus();
            }}
          >
            Clear
          </button>
        ) : null}
        <button
          type="button"
          className="qfil"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((o) => !o)}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            aria-hidden="true"
          >
            <path d="M4 7h16M7 12h10M10 17h4" />
          </svg>
          <span>Filter</span>
        </button>
      </form>
      {open ? (
        <div id={panelId} className="qsug menu" role="group" aria-label="Narrow your search">
          <p className="qh">Narrow it to</p>
          <div className="qopts">
            {filters.map((f) => (
              <button
                key={f.value}
                type="button"
                className={f.count === 0 ? "qopt zero" : "qopt"}
                aria-pressed={picked.includes(f.value)}
                onClick={() => toggle(f.value)}
              >
                {f.label}
                {f.count !== undefined ? <span className="n num">{f.count}</span> : null}
              </button>
            ))}
          </div>
          {asks?.length ? (
            <>
              <p className="qh">Or ask in your own words</p>
              <div className="qasks">
                {asks.map((q) => (
                  <button
                    key={q}
                    type="button"
                    className="qask"
                    onClick={() => {
                      onText(q);
                      setOpen(false);
                      onAsk?.(q);
                    }}
                  >
                    <IconSearch size={16} />
                    <span>{q}</span>
                  </button>
                ))}
              </div>
            </>
          ) : null}
          {foot ? <p className="qfoot">{foot}</p> : null}
        </div>
      ) : null}
      <div className="qans-live" role="status">
        {answer ? (
          <div className="qans">
            <div>
              <p className="qa1">{answer.line}</p>
              {answer.source ? <p className="qa2">{answer.source}</p> : null}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
