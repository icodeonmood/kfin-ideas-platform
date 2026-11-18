/**
 * Coming back to the same place in a list (J-BROWSE, P-ROUTES.state, S-07.return). A list keeps its state in its own
 * URL; when a row is opened, the list's URL (with the row and how far it sat from the top of the window) is written
 * into the destination's `back`, so the destination's Back link returns to the very same view. On arrival the list
 * scrolls the row back to where it was, gives its link focus and washes it once.
 */

/** The destination's address with `back` set to the list's own address (a path on this site; the server checks it
 * again before it links to it). */
export function withBack(to: string, back: string): string {
  const url = new URL(to, "http://x");
  url.searchParams.set("back", back);
  return url.pathname + url.search;
}

/** How far the row sits from the top of the window, in CSS pixels. */
export function rowOffset(el: Element | null): number {
  const row = el?.closest("[data-row]") ?? el;
  return Math.round(row?.getBoundingClientRect().top ?? 0);
}

function visible(el: HTMLElement): boolean {
  return el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden";
}

/**
 * Scrolls the row named `at` back to `dy` pixels from the top of the window (or near the top), focuses its first
 * link without scrolling again, and washes it once (`.is-back`; nothing moves under reduced motion). Returns the row,
 * or null when it is not on the page.
 */
export function restoreRow(root: ParentNode | null, at: string, dy: number | null): HTMLElement | null {
  if (!root) return null;
  const rows = Array.from(root.querySelectorAll<HTMLElement>(`[data-row="${CSS.escape(at)}"]`));
  const row = rows.find(visible);
  if (!row) return null;
  const top = row.getBoundingClientRect().top + window.scrollY - (dy ?? 120);
  window.scrollTo({ top: Math.max(0, top), left: 0, behavior: "instant" });
  row.querySelector<HTMLElement>("a[href], button")?.focus({ preventScroll: true });
  row.classList.remove("is-back");
  // Restart the wash if the same row is restored twice
  void row.offsetWidth;
  row.classList.add("is-back");
  window.setTimeout(() => row.classList.remove("is-back"), 2_400);
  return row;
}
