import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { writeupStep } from "@/server/delivery";
import { asResponse } from "@/server/http";

/** POST /api/delivery/{id}/writeup/approve — the named sponsor (never the submitter) approves and publishes it to "Already running" matches,
 * behind `solutions.publish` (BLD-133). */
export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await writeupStep(me, (await params).id, "approve"));
  } catch (err) {
    return asResponse(err);
  }
}
