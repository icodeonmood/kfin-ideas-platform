import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { itemView } from "@/server/review";

/** GET /api/review/items/{id} — the item screen, restored as far as this viewer may see (§3.1). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("view_review_queue");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await itemView(me, (await params).id), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    return asResponse(err);
  }
}
