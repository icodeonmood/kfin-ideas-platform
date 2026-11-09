import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse, readJson } from "@/server/http";
import { giveAward } from "@/server/ones";

/** POST /api/ones/{id}/awards — The Ones Night: an impact award for the year (DEC-085). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("carry_out_ones");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await giveAward(me, (await params).id, await readJson(request)), {
      status: 201,
    });
  } catch (err) {
    return asResponse(err);
  }
}
