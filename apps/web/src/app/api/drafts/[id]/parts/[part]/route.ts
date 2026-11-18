import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { bodyOf, deviceOf, draftError, drafts, noStore, spansForBrowser } from "@/server/drafts";

/** PATCH /api/drafts/{id}/parts/{part} `{ value }` — the person's own value: set and pinned, so later messages
 * never overwrite it ("Your call", L-DRAFT.pins). `{ pinned: false }` unpins and suggests again ("Suggest again").
 * `part` is title, summary, often, who, value or area. Returns `{ run_id, draft }`. */
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; part: string }> },
) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const body = await bodyOf(request);
  try {
    const { id, part } = await params;
    const path = `${encodeURIComponent(id)}/parts/${encodeURIComponent(part)}`;
    const send = "value" in body ? { value: body.value } : body.pinned === false ? { pinned: false } : {};
    const { body: out } = await drafts.write(me, deviceOf(request), "PATCH", path, send);
    return NextResponse.json(spansForBrowser(out), { headers: noStore });
  } catch (err) {
    return draftError(err);
  }
}
