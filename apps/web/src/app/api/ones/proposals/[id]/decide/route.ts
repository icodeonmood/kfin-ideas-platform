import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse, readJson } from "@/server/http";
import { decide } from "@/server/ones";

/** POST /api/ones/proposals/{id}/decide — Approve or decline: the chair, or a recorded meeting majority. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("decide_ones");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await decide(me, (await params).id, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
