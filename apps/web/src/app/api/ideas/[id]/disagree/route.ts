import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { ideaWrite } from "@/server/review";

/** POST /api/ideas/{id}/disagree — {text} from the idea's own submitter. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(
      await ideaWrite(me, (await params).id, "disagree", await request.json().catch(() => null)),
    );
  } catch (err) {
    return asResponse(err);
  }
}
