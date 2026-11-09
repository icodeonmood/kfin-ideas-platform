import { NextResponse, type NextRequest } from "next/server";

import { fileAppeal, myAppeals } from "@/server/appeals";
import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";

/** GET /api/appeals — committee decisions on my groups and the appeals I hear. POST — appeal one (§4.12). */

export async function GET() {
  const me = await authorize("signed_in");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await myAppeals(me));
  } catch (err) {
    return asResponse(err);
  }
}

export async function POST(request: NextRequest) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const body = ((await request.json().catch(() => null)) ?? {}) as Record<string, unknown>;
  try {
    return NextResponse.json(await fileAppeal(me, body), { status: 201 });
  } catch (err) {
    return asResponse(err);
  }
}
