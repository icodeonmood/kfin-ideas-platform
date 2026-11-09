import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { saveWriteup } from "@/server/delivery";
import { asResponse, readJson } from "@/server/http";

/** PUT /api/delivery/{id}/writeup — the owner drafts the write-up other teams can adopt (BLD-133). Every part is
 * checked for personal data and colleague or client names before it is kept. */
export async function PUT(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await saveWriteup(me, p.id, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
