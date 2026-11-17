import "server-only";

import type { NextResponse } from "next/server";

import type {
  EmberResponse,
  ImpactResponse,
  JustInResponse,
  KindlingResponse,
  OnesResponse,
} from "@/lib/contracts/api";
import { justIn, kindling, wallEmber, wallImpact, wallOnes } from "@/server/wall";

import { DESK_STEP, type Part, type WallData, type WallState } from "./state";

/**
 * The Wall's first view on the server (S-WALL, A-API.wall): the same worker relays the `/api/wall/*` route handlers
 * use, so the page and a later fetch from the screen read the very same body.
 */
async function read<T>(res: Promise<NextResponse>): Promise<Part<T>> {
  try {
    const r = await res;
    const body = (await r.json().catch(() => null)) as unknown;
    if (r.ok && body !== null) return { ok: true, data: body as T };
    const err = (body as { error?: { code?: string; message?: string } } | null)?.error;
    return { ok: false, paused: err?.code === "paused" ? (err.message ?? "") : null };
  } catch {
    return { ok: false, paused: null };
  }
}

export async function loadWall(s: WallState): Promise<WallData> {
  const kindQ = new URLSearchParams(s.kind === "all" ? {} : { kind: s.kind });
  const justQ = new URLSearchParams({
    ...(s.kind === "all" ? {} : { kind: s.kind }),
    sort: s.sort,
    limit: String(DESK_STEP * (s.more + 1)),
    offset: "0",
  });
  const [k, j, o, i, e] = await Promise.all([
    read<KindlingResponse>(kindling(kindQ)),
    read<JustInResponse>(justIn(justQ)),
    read<OnesResponse>(wallOnes(new URLSearchParams({ order: s.ones }))),
    read<ImpactResponse>(wallImpact()),
    read<EmberResponse>(wallEmber()),
  ]);
  return { kindling: k, justIn: j, ones: o, impact: i, ember: e };
}
