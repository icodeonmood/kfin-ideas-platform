import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { addMilestone } from "@/server/delivery";
import { asResponse, readJson } from "@/server/http";

/** POST /api/delivery/{id}/milestones — Fix track: add a milestone to the action plan (§4.10). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await addMilestone(me, p.id, await readJson(request)), { status: 201 });
  } catch (err) {
    return asResponse(err);
  }
}
