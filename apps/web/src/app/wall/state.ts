import type {
  EmberResponse,
  ImpactResponse,
  JustInResponse,
  KindlingResponse,
  OnesResponse,
} from "@/lib/contracts/api";
import { isEnumValue, type Kind, type WallSort } from "@/lib/contracts/enums";

/**
 * One part of the Wall as read from `/api/wall/*` (A-API.wall): its body, or that it could not be read. `paused`
 * carries a kill switch's notice (§7.6) when the part is switched off, else null. Each part loads on its own, and a
 * missing part is said in its place, never a blank area (C-EMPTY).
 */
export type Part<T> = { ok: true; data: T } | { ok: false; paused: string | null };

export type WallData = {
  kindling: Part<KindlingResponse>;
  justIn: Part<JustInResponse>;
  ones: Part<OnesResponse>;
  impact: Part<ImpactResponse>;
  ember: Part<EmberResponse>;
};

/** The Wall's state in its own URL (P-ROUTES.state, J-BROWSE/5): kind chip, Just in's sort, how far Just in is
 * opened ("Show 5 more" pressed `more` times), the Ones in leaderboard order, and the row to come back to with how
 * far it sat from the top of the window. */
export type WallState = {
  kind: Kind | "all";
  sort: WallSort;
  more: number;
  ones: "wall" | "leaderboard";
  at: string | null;
  dy: number | null;
};

/** Desktop pages Just in five at a time (L-WALL.justin/5); the phone shows three of the same rows at a time. */
export const DESK_STEP = 5;
export const PHONE_STEP = 3;

const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? "";

export function wallState(sp: Record<string, string | string[] | undefined>): WallState {
  const kind = first(sp.kind);
  const sort = first(sp.sort);
  const more = Number(first(sp.more));
  const dyRaw = first(sp.dy);
  const dy = Number(dyRaw);
  const at = first(sp.at);
  return {
    kind: isEnumValue("kind", kind) ? kind : "all",
    sort: isEnumValue("wall_sort", sort) ? sort : "newest",
    more: Number.isInteger(more) && more > 0 ? Math.min(more, 9) : 0,
    ones: first(sp.ones) === "leaderboard" ? "leaderboard" : "wall",
    at: /^[A-Za-z0-9-]{1,40}$/.test(at) ? at : null,
    dy: dyRaw !== "" && Number.isFinite(dy) ? Math.max(-4000, Math.min(4000, Math.round(dy))) : null,
  };
}

/** The Wall's own address for a state; defaults are left out, so a plain visit is plain `/wall`. */
export function wallHref(
  s: Pick<WallState, "kind" | "sort" | "more" | "ones">,
  at?: string,
  dy?: number,
): string {
  const q = new URLSearchParams();
  if (s.kind !== "all") q.set("kind", s.kind);
  if (s.sort !== "newest") q.set("sort", s.sort);
  if (s.more > 0) q.set("more", String(s.more));
  if (s.ones === "leaderboard") q.set("ones", "leaderboard");
  if (at) q.set("at", at);
  if (at && dy !== undefined) q.set("dy", String(dy));
  const qs = q.toString();
  return qs ? `/wall?${qs}` : "/wall";
}
