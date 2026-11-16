"use client";

import { useRef, type KeyboardEvent, type ReactNode } from "react";

/**
 * C-TABS: text tabs with counts. tablist, tab and aria-selected; arrow keys, Home and End move between tabs and
 * select them; one tab stop. A tab with a zero count stays and its panel shows an empty state (C-TABS/5). The screen
 * keeps the tab in the URL and renders the panel with `tabPanelProps`.
 */
export type TabDef = { value: string; label: string; count?: number };

export function tabId(base: string, value: string) {
  return `${base}-tab-${value}`;
}

export function tabPanelProps(base: string, value: string) {
  return {
    id: `${base}-panel-${value}`,
    role: "tabpanel" as const,
    "aria-labelledby": tabId(base, value),
    tabIndex: 0,
  };
}

export function Tabs({
  id,
  label,
  tabs,
  value,
  onChange,
}: {
  /** A stable base for the tab and panel ids. */
  id: string;
  label: string;
  tabs: TabDef[];
  value: string;
  onChange: (value: string) => void;
}) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const at = Math.max(
    0,
    tabs.findIndex((t) => t.value === value),
  );
  const go = (i: number) => {
    const t = tabs[i];
    if (!t) return;
    onChange(t.value);
    refs.current[i]?.focus();
    refs.current[i]?.scrollIntoView({ block: "nearest", inline: "nearest" });
  };
  const onKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    const n = tabs.length;
    const to =
      e.key === "ArrowRight"
        ? (at + 1) % n
        : e.key === "ArrowLeft"
          ? (at - 1 + n) % n
          : e.key === "Home"
            ? 0
            : e.key === "End"
              ? n - 1
              : -1;
    if (to < 0) return;
    e.preventDefault();
    go(to);
  };
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {tabs.map((t, i): ReactNode => (
        <button
          key={t.value}
          ref={(el) => {
            refs.current[i] = el;
          }}
          id={tabId(id, t.value)}
          type="button"
          role="tab"
          aria-selected={i === at}
          aria-controls={`${id}-panel-${t.value}`}
          tabIndex={i === at ? 0 : -1}
          onClick={() => go(i)}
          onKeyDown={onKey}
        >
          {t.label}
          {t.count !== undefined ? <span className="tab-n">{t.count}</span> : null}
        </button>
      ))}
    </div>
  );
}
