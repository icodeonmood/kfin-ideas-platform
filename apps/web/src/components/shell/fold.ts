/** The sidebar's fold choice (C-SIDEBAR.fold/3), remembered per person and device in a cookie the layout reads, so the
 * first paint already has the right width. The value names the person, so a shared device never hands one person's
 * choice to the next. */
export const FOLD_COOKIE = "pc_fold";

export function foldValue(personId: string, folded: boolean): string {
  return `${folded ? "f" : "o"}.${personId}`;
}

/** true folded, false open, null when this person has not chosen (the width decides: folded at 1100 px and below). */
export function foldedFrom(cookie: string | undefined, personId: string | undefined): boolean | null {
  if (!cookie || !personId) return null;
  if (cookie === foldValue(personId, true)) return true;
  if (cookie === foldValue(personId, false)) return false;
  return null;
}
