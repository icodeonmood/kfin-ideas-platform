"use client";
/**
 * C-DRAFT-LOADER: one bar for six independent parts (BLD-C120). The fill follows `lib/compose/loader.ts`; the strip
 * folds away a moment after "All 6 parts are in". A run that ends with a part still waiting for words is not all in:
 * no fill to 100%, no pop and no line of its own, the strip just folds (BLD-C157). `role="progressbar"`, its value
 * told at most once a second, with the visible line as its text (C-DRAFT-LOADER.a11y). Reduced motion: no sweep, no
 * bead pulse (CSS).
 */
import { useEffect, useState } from "react";

import { barValue, LOADER_ALL_IN, LOADER_TITLE, loaderLine, type LoaderRun } from "@/lib/compose/loader";

const TICK_MS = 200;
const HOLD_MS = 900; // "after a short hold the strip folds away" (maths/7)

/** The page's clock while a run builds: the bar, its line and the phone peek's line move with it. */
export function useLoaderClock(run: LoaderRun | null, done: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!run || done) return;
    const t = setInterval(() => setNow(Date.now()), TICK_MS);
    return () => clearInterval(t);
  }, [run, done]);
  return now;
}

export function DraftLoader({
  run,
  done,
  ended = done,
  phone = false,
  now: fixedNow,
}: {
  run: LoaderRun | null;
  /** All six parts are in and nothing is building (`allIn`): the bar fills, the bead pops, the line reads "All 6
   * parts are in", and the strip folds after a short hold (maths/7). */
  done: boolean;
  /** The run has finished. Without all six in, the strip folds away at once and quietly (BLD-C157). */
  ended?: boolean;
  phone?: boolean;
  /** A clock from outside (the phone peek shares its own), or a fixed one in tests. */
  now?: number;
}) {
  const over = done || ended;
  const ticking = useLoaderClock(fixedNow === undefined ? run : null, over);
  const [folded, setFolded] = useState<LoaderRun | null>(null);
  // How this run ended, settled once when it ends: a later read of the draft or a part changed by hand never replays
  // "All 6 parts are in" for it, nor cuts its hold short (BLD-C157).
  const [end, setEnd] = useState<{ run: LoaderRun; all: boolean } | null>(null);
  if (run && over && end?.run !== run) setEnd({ run, all: done });
  const all = run !== null && end?.run === run ? end.all : done;

  useEffect(() => {
    if (!over || !run) return;
    const t = setTimeout(() => setFolded(run), all ? HOLD_MS : 0);
    return () => clearTimeout(t);
  }, [over, all, run]);

  if (!run) return null;
  const at = fixedNow ?? ticking;
  // The sum only grows with time and answers, so the bar never moves back (maths/4).
  const value = all ? 1 : barValue(run, at);
  const line = all ? LOADER_ALL_IN : loaderLine(run, at);
  // Told to screen readers at most once a second: the value at the start of this second.
  const told = all ? 100 : Math.round(barValue(run, Math.floor(at / 1000) * 1000) * 100);
  // Ended without all six in: it folds at once and stays folded, so nothing fills, pops or says it is all in.
  const isFolded = folded === run || (over && !all);

  return (
    <div
      className={`dload${phone ? " ph" : ""}${all ? " all" : ""}${isFolded ? " fold" : ""}`}
      aria-hidden={isFolded ? true : undefined}
    >
      {phone ? null : (
        <div className="dl-top">
          <span className="dl-t">{LOADER_TITLE}</span>
          <span className="dl-n">{line}</span>
        </div>
      )}
      <span
        className="dl-tube"
        role="progressbar"
        aria-label={LOADER_TITLE}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={told}
        aria-valuetext={line}
        style={{ ["--p" as string]: value }}
      >
        <span className="dl-fill" />
        <span className="dl-bead" />
      </span>
    </div>
  );
}
