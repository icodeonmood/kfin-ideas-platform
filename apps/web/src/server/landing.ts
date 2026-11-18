/**
 * S-01 Landing's two reads (S-01.rules/2-3). Both already degrade: no review time says who reviews, not when; no
 * Ones leaves the slab out. So neither may hold the front door on a slow worker: each waits at most LANDING_WAIT_MS,
 * then the page draws without it (BLD-A172). A late answer still fills the promises cache for the next visitor.
 */
import { publicOnes, type PublicOne } from "./ones";
import { promises } from "./promises";

export const LANDING_WAIT_MS = 1_500;

/** The read's answer, or the fallback if it fails or takes longer than `ms`. */
export function atMost<T>(read: () => Promise<T>, fallback: T, ms = LANDING_WAIT_MS): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const late = new Promise<T>((resolve) => {
    timer = setTimeout(() => resolve(fallback), ms);
  });
  const answer = Promise.resolve()
    .then(read)
    .catch(() => fallback);
  return Promise.race([answer, late]).finally(() => clearTimeout(timer));
}

/** "Within 5 working days": `review.decide_by_working_days` from rules/promises.md, or null. */
export const reviewDays = (ms = LANDING_WAIT_MS): Promise<number | null> =>
  atMost(
    async () => {
      const days = (await promises()).review.decide_by_working_days;
      return Number.isFinite(days) && days > 0 ? days : null;
    },
    null,
    ms,
  );

/** The three most recent Ones with a public brief; none if they cannot be read in time. */
export const landingOnes = (ms = LANDING_WAIT_MS): Promise<PublicOne[]> =>
  atMost(async () => (await publicOnes(ms)).ones.slice(0, 3), [], ms);
