import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { learning } from "@/server/delivery";
import { asResponse } from "@/server/http";

/** GET /api/learning — The learning loops' reports and proposals (§5). */
export async function GET() {
  const me = await authorize("review_learning");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await learning(me));
  } catch (err) {
    return asResponse(err);
  }
}
