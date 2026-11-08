import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { ideaPage } from "@/server/ideas";

/** GET /api/ideas/{IDEA-…} — the idea page in the view §3.1 allows this person (AT-B7-03). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("see_org_ideas");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await ideaPage(me, (await params).id), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    return asResponse(err);
  }
}
