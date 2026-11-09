import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { deliveryConsole, startHandover } from "@/server/delivery";
import { asResponse, readJson } from "@/server/http";

/** GET /api/delivery — Your deliveries; committee members and admins see all, and the picked ideas waiting for a handover. */
export async function GET() {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await deliveryConsole(me));
  } catch (err) {
    return asResponse(err);
  }
}

/** POST /api/delivery — Start the handover for a picked idea or group (§4.8). */
export async function POST(request: NextRequest) {
  const me = await authorize("start_handover");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await startHandover(me, await readJson(request)), { status: 201 });
  } catch (err) {
    return asResponse(err);
  }
}
