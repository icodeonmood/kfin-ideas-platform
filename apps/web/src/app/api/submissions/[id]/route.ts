import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse, readJson } from "@/server/http";
import { getDraft, saveDraft } from "@/server/submissions";

type Params = { params: Promise<{ id: string }> };

/** GET /api/submissions/{id} — resume my draft (owner only). */
export async function GET(_request: NextRequest, { params }: Params) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await getDraft(me, (await params).id), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    return asResponse(err);
  }
}

/** PUT /api/submissions/{id} {canvas} — autosave (§4.1 step 2). Refuses blocking personal data with 422. */
export async function PUT(request: NextRequest, { params }: Params) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await saveDraft(me, (await params).id, (await readJson(request)).canvas));
  } catch (err) {
    return asResponse(err);
  }
}
