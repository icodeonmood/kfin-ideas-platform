import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { queue } from "@/server/review";

/** GET /api/review/items — the open queue with filters (type, kind, lob, category, strength, band, age). */
export async function GET(request: NextRequest) {
  const me = await authorize("view_review_queue");
  if (me instanceof NextResponse) return me;
  const p = request.nextUrl.searchParams;
  const f = Object.fromEntries(
    ["type", "kind", "lob", "category", "strength", "band", "age"].map((k) => [k, p.get(k) ?? undefined]),
  );
  return NextResponse.json({ items: await queue(f) }, { headers: { "Cache-Control": "no-store" } });
}
