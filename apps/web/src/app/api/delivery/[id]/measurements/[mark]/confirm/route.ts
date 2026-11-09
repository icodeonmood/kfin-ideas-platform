import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { confirmMeasurement } from "@/server/delivery";
import { asResponse } from "@/server/http";

/** POST /api/delivery/{id}/measurements/{mark}/confirm — The sponsor confirms a measurement (never their own entry). */
export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string; mark: string }> },
) {
  const me = await authorize("approve_handover");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await confirmMeasurement(me, p.id, p.mark));
  } catch (err) {
    return asResponse(err);
  }
}
