import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { similarIdeas } from "@/server/similar";

/** GET /api/ideas/{IDEA-… or row ID}/similar — SimilarMatch[] (L-SIMILAR, C-SIMGRID). The sharer of the draft or
 * idea, or the review desk and the Ones Committee; anyone else gets 404 (BLD-C092). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("see_org_ideas");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await similarIdeas(me, (await params).id), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    return asResponse(err);
  }
}
