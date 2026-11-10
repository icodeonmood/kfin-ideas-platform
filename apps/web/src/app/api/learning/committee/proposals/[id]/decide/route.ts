import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { decideLearning } from "@/server/delivery";
import { asResponse, readJson } from "@/server/http";

/** POST /api/learning/committee/proposals/{id}/decide — The chair (scorecard weights) or the core committee
 * (scoring bands) approves or declines. Approval records the decision; no rule changes on its own. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("approve_scorecard_changes");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await decideLearning(me, p.id, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
