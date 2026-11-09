import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { runLearning } from "@/server/delivery";
import { asResponse, readJson } from "@/server/http";

/** POST /api/learning/run — Run one learning loop now (behind learning.jobs). */
export async function POST(request: NextRequest) {
  const me = await authorize("review_learning");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await runLearning(me, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
