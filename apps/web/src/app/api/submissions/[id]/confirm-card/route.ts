import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { confirmCard } from "@/server/scan";

/** POST /api/submissions/{id}/confirm-card — {keep: {path: boolean}, one_line?, details?} ("Looks right"). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const body = await request.json().catch(() => null);
  try {
    return NextResponse.json(await confirmCard(me, (await params).id, body));
  } catch (err) {
    return asResponse(err);
  }
}
