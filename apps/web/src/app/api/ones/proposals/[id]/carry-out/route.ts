import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { carryOut } from "@/server/ones";

/** POST /api/ones/proposals/{id}/carry-out — The admin member carries out an approved proposal and the message goes. */
export async function POST(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("carry_out_ones");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await carryOut(me, (await params).id));
  } catch (err) {
    return asResponse(err);
  }
}
