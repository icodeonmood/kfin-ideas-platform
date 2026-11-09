import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { savePack } from "@/server/delivery";
import { asResponse, readJson } from "@/server/http";

/** PUT /api/delivery/{id}/pack — Save the handover pack (owner, sponsor, metric, spend, checklist). */
export async function PUT(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await savePack(me, p.id, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
