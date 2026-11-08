import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { chooseMatch } from "@/server/scan";

/** POST /api/submissions/{id}/choose — {choice, ref?, text?}: team up, +1, mine is different, something has
 * changed, share as new, or withdraw. Saved in one transaction (§4.2 step 8). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const body = await request.json().catch(() => null);
  try {
    return NextResponse.json(await chooseMatch(me, (await params).id, body));
  } catch (err) {
    return asResponse(err);
  }
}
