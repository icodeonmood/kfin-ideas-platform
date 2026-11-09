import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse, readJson } from "@/server/http";
import { propose } from "@/server/ones";

/** POST /api/ones/proposals — Propose a One, a removal, a tier change or a legend number (DEC-040, DEC-045, DEC-076, DEC-082). */
export async function POST(request: NextRequest) {
  const me = await authorize("propose_ones");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await propose(me, await readJson(request)), { status: 201 });
  } catch (err) {
    return asResponse(err);
  }
}
