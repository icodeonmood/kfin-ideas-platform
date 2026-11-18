/**
 * The review desk's own address (S-R1.rules/4, J-BROWSE/4, P-ROUTES.state): the tab and sort of the list, and, while
 * an idea is open from it, the row that was opened and how far it sat from the top of the window, so Back returns to
 * the same list with that row where it was (the Wall's and My ideas' pattern, `browse/return-to`). The search is
 * never in it (DEC-110): it stays in this tab's memory of the history entry (`lib/search-memory`) and goes to the
 * server in a request body.
 */
import type { DeskSort, DeskTab } from "@/lib/contracts";

const TABS: readonly DeskTab[] = ["to_review", "waiting", "answered", "decided"];
const SORTS: readonly DeskSort[] = ["time_left", "decide_by", "area"];

/** A list on the desk: its tab, its sort and the search it was read for. */
export type DeskList = { tab: DeskTab; sort: DeskSort; q: string };

export type DeskAddress = {
  tab: DeskTab | null;
  sort: DeskSort | null;
  /** The row to come back to, and its offset from the top of the window in CSS pixels */
  row: string | null;
  dy: number | null;
};

/** The tab and sort an address asks for, or null for any it does not name; and the row to come back to. A `q` in an
 * older address is not read: a link never brings a search with it (J-BROWSE/6). */
export function deskUrlState(search: string): DeskAddress {
  const sp = new URLSearchParams(search);
  const row = sp.get("row") || null;
  const dy = row && sp.get("dy") ? Number(sp.get("dy")) : NaN;
  return {
    tab: TABS.find((t) => t === sp.get("tab")) ?? null,
    sort: SORTS.find((s) => s === sp.get("sort")) ?? null,
    row,
    dy: Number.isFinite(dy) ? Math.round(dy) : null,
  };
}

/** The desk's address for a list: tab and sort always, then the row opened from it. Never the search. */
export function deskHref(list: Pick<DeskList, "tab" | "sort">, row?: string, dy?: number): string {
  const p = new URLSearchParams({ tab: list.tab, sort: list.sort });
  if (row) p.set("row", row);
  if (row && dy !== undefined && Number.isFinite(dy)) p.set("dy", String(Math.round(dy)));
  return `/desk?${p.toString()}`;
}

/** A list that could not be read leaves the one on screen in place: the address to put back so it names that list
 * again, or null when the address already does (the search, kept apart, is put back by the caller). */
export function addressBack(shown: DeskList, asked: DeskList): string | null {
  return shown.tab === asked.tab && shown.sort === asked.sort ? null : deskHref(shown);
}

/** The body of a desk read with a search (`POST /api/desk`, DEC-110). */
export function deskSearchBody(list: DeskList): string {
  return JSON.stringify({ tab: list.tab, sort: list.sort, q: list.q });
}
