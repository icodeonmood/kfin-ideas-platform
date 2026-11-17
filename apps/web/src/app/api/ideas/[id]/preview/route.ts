import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { ideaPreview } from "@/server/similar";

/** GET /api/ideas/{IDEA-… or row ID}/preview[?compare_with=<id>] — IdeaPreview (A-API.idea-preview, C-PREVIEW).
 * Masked text only; `compare` (and `compare_with`) for the review desk and the Ones Committee (BLD-C090). */
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("see_org_ideas");
  if (me instanceof NextResponse) return me;
  try {
    const compareWith = request.nextUrl.searchParams.get("compare_with");
    return NextResponse.json(await ideaPreview(me, (await params).id, compareWith), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    return asResponse(err);
  }
}
