import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { checkIn } from "@/server/delivery";
import { asResponse, readJson } from "@/server/http";

/** POST /api/delivery/{id}/checkin — the fix track's Friday check-in, answered on the page (BLD-132). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await checkIn(me, p.id, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
