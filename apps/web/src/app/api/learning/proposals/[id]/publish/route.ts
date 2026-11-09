import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { publishProposal } from "@/server/delivery";
import { asResponse, readJson } from "@/server/http";

/** POST /api/learning/proposals/{id}/publish — An admin writes an approved term or tag into the company repo: the
 * text is checked here and the repo writer does the writing, from the outbox (BLD-136). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("review_learning");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await publishProposal(me, p.id, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
