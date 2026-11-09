import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { deliveryDetail } from "@/server/delivery";
import { asResponse } from "@/server/http";

/** GET /api/delivery/{id} — One delivery, for the people working on it. */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    const out = await deliveryDetail(me, (await params).id);
    if (!out) return NextResponse.json({ error: "not_found" }, { status: 404 });
    return NextResponse.json(out, { headers: { "Cache-Control": "no-store" } });
  } catch (err) {
    return asResponse(err);
  }
}
