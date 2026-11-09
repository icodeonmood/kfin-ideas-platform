import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { setPhase } from "@/server/delivery";
import { asResponse, readJson } from "@/server/http";

/** POST /api/delivery/{id}/phase — The delivery PM or an admin records the phase and gate status (§4.9). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await setPhase(me, p.id, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
