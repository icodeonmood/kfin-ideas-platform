import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { committeeLearning } from "@/server/delivery";
import { asResponse } from "@/server/http";

/** GET /api/learning/committee — What the platform learns from the core committee's decisions (§5.9). */
export async function GET() {
  const me = await authorize("approve_scorecard_changes");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await committeeLearning(me));
  } catch (err) {
    return asResponse(err);
  }
}
