import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { approvePack } from "@/server/delivery";
import { asResponse } from "@/server/http";

/** POST /api/delivery/{id}/approve — The named sponsor approves the pack; the work starts. */
export async function POST(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("approve_handover");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await approvePack(me, p.id));
  } catch (err) {
    return asResponse(err);
  }
}
