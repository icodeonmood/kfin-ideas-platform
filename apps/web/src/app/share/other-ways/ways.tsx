"use client";

import { useEffect, useRef, useState } from "react";

const COPIED_FOR_MS = 2000;

/** The 1% Club address with "Copy": the button reads "Copied" for two seconds, said politely, and no toast
 * (S-H3.rules/1). */
export function CopyAddress({ address }: { address: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(address);
    } catch {
      return; // the browser refused: the address is on screen to copy by hand
    }
    setCopied(true);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setCopied(false), COPIED_FOR_MS);
  }

  return (
    <div className="wy-addr">
      <span className="wy-aval">{address}</span>
      <button type="button" className="wy-copy" aria-label="Copy the address" onClick={copy}>
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <rect x="8" y="8" width="12" height="12" rx="2" />
          <path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" />
        </svg>
        <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
      </button>
    </div>
  );
}

/** "Tell me when it's out": stored per person (L-NOTIFY/7); pressed, it reads "We'll tell you when it's out".
 * Pressing it again withdraws the ask. If saving fails, the button stays as it was. */
export function AppNewsButton({ initial }: { initial: boolean }) {
  const [want, setWant] = useState(initial);
  const [busy, setBusy] = useState(false);

  async function toggle() {
    if (busy) return;
    setBusy(true);
    try {
      const res = await fetch("/api/me/app-news", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ want: !want }),
      });
      if (res.ok) setWant(((await res.json()) as { want: boolean }).want);
    } catch {
      // offline: nothing changed, so the button keeps its state
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      className={want ? "wy-btn wy-bell is-on" : "wy-btn wy-bell"}
      aria-pressed={want}
      onClick={toggle}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2h-15z" />
        <path d="M10 20.5a2 2 0 0 0 4 0" />
      </svg>
      {want ? "We’ll tell you when it’s out" : "Tell me when it’s out"}
    </button>
  );
}
