import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { deviceOf, draftError, drafts, noStore } from "@/server/drafts";

/** POST /api/drafts/{id}/restore — an archived draft back among the person's drafts, from My ideas → Drafts
 * (L-DRAFT.autosave/8; addition to A-API.drafts). Returns `Draft`. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  try {
    const id = encodeURIComponent((await params).id);
    const { body } = await drafts.write(me, deviceOf(request), "POST", `${id}/restore`);
    return NextResponse.json(body, { headers: noStore });
  } catch (err) {
    return draftError(err);
  }
}
