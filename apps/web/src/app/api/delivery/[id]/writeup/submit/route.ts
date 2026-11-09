import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { writeupStep } from "@/server/delivery";
import { asResponse } from "@/server/http";

/** POST /api/delivery/{id}/writeup/submit — the owner submits the write-up to the named sponsor (BLD-133). */
export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await writeupStep(me, (await params).id, "submit"));
  } catch (err) {
    return asResponse(err);
  }
}
