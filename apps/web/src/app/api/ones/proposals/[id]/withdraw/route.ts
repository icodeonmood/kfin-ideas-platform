import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { withdraw } from "@/server/ones";

/** POST /api/ones/proposals/{id}/withdraw — The proposer withdraws their proposal. */
export async function POST(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("propose_ones");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await withdraw(me, (await params).id));
  } catch (err) {
    return asResponse(err);
  }
}
