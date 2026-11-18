/**
 * The review desk's own address (S-R1.rules/4, J-BROWSE/4, P-ROUTES.state): the tab, sort and search of the list,
 * and, while an idea is open from it, the row that was opened and how far it sat from the top of the window, so Back
 * returns to the same list with that row where it was (the Wall's and My ideas' pattern, `browse/return-to`).
 */
import type { DeskSort, DeskTab } from "@/lib/contracts";

const TABS: readonly DeskTab[] = ["to_review", "waiting", "answered", "decided"];
const SORTS: readonly DeskSort[] = ["time_left", "decide_by", "area"];

/** A list on the desk: its tab, its sort and the search it was read for. */
export type DeskList = { tab: DeskTab; sort: DeskSort; q: string };

export type DeskAddress = {
  tab: DeskTab | null;
  sort: DeskSort | null;
  q: string;
  /** The row to come back to, and its offset from the top of the window in CSS pixels */
  row: string | null;
  dy: number | null;
};

/** The tab, sort and search an address asks for, or null for any it does not name; and the row to come back to. */
export function deskUrlState(search: string): DeskAddress {
  const sp = new URLSearchParams(search);
  const row = sp.get("row") || null;
  const dy = row && sp.get("dy") ? Number(sp.get("dy")) : NaN;
  return {
    tab: TABS.find((t) => t === sp.get("tab")) ?? null,
    sort: SORTS.find((s) => s === sp.get("sort")) ?? null,
    q: (sp.get("q") ?? "").slice(0, 200),
    row,
    dy: Number.isFinite(dy) ? Math.round(dy) : null,
  };
}

/** The desk's address for a list: tab and sort always, the search when there is one, then the row opened from it. */
export function deskHref(list: DeskList, row?: string, dy?: number): string {
  const p = new URLSearchParams({ tab: list.tab, sort: list.sort });
  if (list.q) p.set("q", list.q);
  if (row) p.set("row", row);
  if (row && dy !== undefined && Number.isFinite(dy)) p.set("dy", String(Math.round(dy)));
  return `/desk?${p.toString()}`;
}
