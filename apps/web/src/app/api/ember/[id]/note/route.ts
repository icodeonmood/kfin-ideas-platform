import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { emberNote } from "@/server/ember";
import { asResponse, readJson } from "@/server/http";

/** PUT /api/ember/{id}/note — The chair (or an admin) saves "What the committee looks for" (BLD-128). */
export async function PUT(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("write_ember_note");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await emberNote(me, (await params).id, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
