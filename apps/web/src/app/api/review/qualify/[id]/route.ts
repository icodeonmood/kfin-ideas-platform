import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { qualifyAct, qualifyView } from "@/server/committee";
import { asResponse } from "@/server/http";

/** GET and POST /api/review/qualify/{id} — the desk's qualify item (§4.5). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("view_review_queue");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await qualifyView(me, (await params).id), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    return asResponse(err);
  }
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("work_review_queue");
  if (me instanceof NextResponse) return me;
  const body = ((await request.json().catch(() => null)) ?? {}) as Record<string, unknown>;
  try {
    return NextResponse.json(await qualifyAct(me, (await params).id, body));
  } catch (err) {
    return asResponse(err);
  }
}
