import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { setMilestone } from "@/server/delivery";
import { asResponse, readJson } from "@/server/http";

/** POST /api/delivery/{id}/milestones/{ms} — Fix track: mark a milestone done or open again. */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; ms: string }> },
) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await setMilestone(me, p.id, p.ms, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
