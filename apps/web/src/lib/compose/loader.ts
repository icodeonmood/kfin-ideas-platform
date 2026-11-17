/**
 * C-DRAFT-LOADER.maths as pure steps (S-04, S-04B; BLD-C120): six parts called together, one bar that never pauses
 * and never moves back. The server sends only each part's mean (`run` event, A-API.draft-stream); the bar, the count,
 * the estimate and the slow-part line are worked out here from those means and the time since the run started.
 */
import type { DraftPartKey } from "@/lib/contracts";

export type LoaderPart = { key: DraftPartKey; mean_ms: number };
export type LoaderRun = {
  parts: LoaderPart[];
  startedAt: number;
  answered: Partial<Record<DraftPartKey, number>>;
};

/** C-DRAFT-LOADER.maths/6: the two slow-part lines the pack draws. The other four have none ("and so on" is not
 * copy), so a slow one of those keeps the estimate line (listed as missing copy, BLD-C120). */
export const SLOW_LINE: Partial<Record<DraftPartKey, string>> = {
  similar: "still looking for similar ideas",
  title: "the title is taking longer",
};

export const LOADER_TITLE = "Building your draft";
export const LOADER_ALL_IN = "All 6 parts are in";
const CAP = 0.97; // C-DRAFT-LOADER.maths/4
const SLOW = 1.5; // maths/6
const GIVE_UP = 10; // failure/1: past 10 × its mean a part stops counting as pending

const mean = (p: LoaderPart) => Math.max(1, p.mean_ms);

/** maths/2: a pending part's progress, always rising, never full on its own. */
export function partProgress(elapsedMs: number, meanMs: number): number {
  if (elapsedMs <= 0) return 0;
  return 0.9 * (1 - Math.exp(-elapsedMs / Math.max(1, meanMs)));
}

export function isAnswered(run: LoaderRun, key: DraftPartKey, now: number): boolean {
  if (run.answered[key] !== undefined) return true;
  const p = run.parts.find((x) => x.key === key);
  return p ? now - run.startedAt > GIVE_UP * mean(p) : true;
}

/** Parts past 10 × their mean, treated as failed (failure/1). */
export function givenUp(run: LoaderRun, now: number): DraftPartKey[] {
  return run.parts
    .filter((p) => run.answered[p.key] === undefined && now - run.startedAt > GIVE_UP * mean(p))
    .map((p) => p.key);
}

/** maths/4: the weighted sum, capped at 97% until every part is in. Weights are shares of the summed means. */
export function barValue(run: LoaderRun, now: number): number {
  if (!run.parts.length) return 1;
  const total = run.parts.reduce((s, p) => s + mean(p), 0);
  const t = now - run.startedAt;
  let sum = 0;
  let all = true;
  for (const p of run.parts) {
    const w = mean(p) / total;
    if (isAnswered(run, p.key, now)) sum += w;
    else {
      all = false;
      sum += w * partProgress(t, mean(p));
    }
  }
  return all ? 1 : Math.min(CAP, sum);
}

export function readyCount(run: LoaderRun, now: number): number {
  return run.parts.filter((p) => isAnswered(run, p.key, now)).length;
}

/** The right-hand line: "2 of 6 ready, about 2 seconds left", "almost there", or a slow part's own line. */
export function loaderLine(run: LoaderRun, now: number): string {
  const total = run.parts.length;
  const n = readyCount(run, now);
  if (n >= total) return LOADER_ALL_IN;
  const t = now - run.startedAt;
  const pending = run.parts.filter((p) => !isAnswered(run, p.key, now));
  const slow = pending.find((p) => t > SLOW * mean(p) && SLOW_LINE[p.key]);
  const head = `${n} of ${total} ready, `;
  if (slow) return head + SLOW_LINE[slow.key];
  const left = Math.max(...pending.map((p) => mean(p) - t));
  if (left < 1000) return head + "almost there";
  const s = Math.round(left / 1000);
  return `${head}about ${s} ${s === 1 ? "second" : "seconds"} left`;
}
