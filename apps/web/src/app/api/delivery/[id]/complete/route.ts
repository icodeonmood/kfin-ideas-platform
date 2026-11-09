import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { completeFix } from "@/server/delivery";
import { asResponse, readJson } from "@/server/http";

/** POST /api/delivery/{id}/complete — Fix track: the owner submits before-and-after numbers. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await completeFix(me, p.id, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
