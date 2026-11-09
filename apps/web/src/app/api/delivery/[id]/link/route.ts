import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { linkPage } from "@/server/delivery";
import { asResponse, readJson } from "@/server/http";

/** POST /api/delivery/{id}/link — An admin links the delivery pipeline's page by hand (live sync is coming soon). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("manage_delivery");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await linkPage(me, p.id, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
