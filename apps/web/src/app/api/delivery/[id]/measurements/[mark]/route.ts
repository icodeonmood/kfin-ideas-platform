import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { fillMeasurement } from "@/server/delivery";
import { asResponse, readJson } from "@/server/http";

/** PUT /api/delivery/{id}/measurements/{mark} — The owner fills the 30- or 90-day measurement (§4.11). */
export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; mark: string }> },
) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await fillMeasurement(me, p.id, p.mark, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
