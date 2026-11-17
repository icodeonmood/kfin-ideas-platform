import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { bodyOf, deviceOf, draftError, drafts, noStore } from "@/server/drafts";

type Params = { params: Promise<{ id: string }> };

/** GET /api/drafts/{id}[?open=1] — the draft, owner only, exactly as left: messages in the person's own words,
 * parts and pins, sorting, step, and "last saved on your phone, Friday 8:42 pm" (L-DRAFT.autosave/2–4). `open=1`
 * makes this device the one editor (L-DRAFT.autosave/5). */
export async function GET(request: NextRequest, { params }: Params) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  try {
    const open = request.nextUrl.searchParams.get("open") === "1";
    const { body } = await drafts.get(me, deviceOf(request), (await params).id, open);
    return NextResponse.json(body, { headers: noStore });
  } catch (err) {
    return draftError(err);
  }
}

/** PATCH /api/drafts/{id} `{ step }` — where the person is; saved at once (L-DRAFT.autosave/1). */
export async function PATCH(request: NextRequest, { params }: Params) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const body = await bodyOf(request);
  try {
    const id = encodeURIComponent((await params).id);
    const { body: out } = await drafts.write(me, deviceOf(request), "PATCH", id, { step: body.step });
    return NextResponse.json(out, { headers: noStore });
  } catch (err) {
    return draftError(err);
  }
}

/** DELETE /api/drafts/{id} — archives the draft; nothing is deleted (L-DRAFT.autosave/8). */
export async function DELETE(request: NextRequest, { params }: Params) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  try {
    const id = encodeURIComponent((await params).id);
    await drafts.write(me, deviceOf(request), "POST", `${id}/archive`);
    return new NextResponse(null, { status: 204, headers: noStore });
  } catch (err) {
    return draftError(err);
  }
}
