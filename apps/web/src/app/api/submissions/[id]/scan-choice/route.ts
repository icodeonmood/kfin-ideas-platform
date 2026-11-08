import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { scanChoice } from "@/server/scan";

/** POST /api/submissions/{id}/scan-choice — {choice: edit | not_personal_data | take_redirect | is_an_idea, reason?} */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const body = await request.json().catch(() => null);
  try {
    return NextResponse.json(await scanChoice(me, (await params).id, body));
  } catch (err) {
    return asResponse(err);
  }
}
