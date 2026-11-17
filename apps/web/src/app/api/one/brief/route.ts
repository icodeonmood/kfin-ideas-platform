import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { objectBody, oneBrief } from "@/server/wall";

/**
 * POST /api/one/brief — {text}: a One proposes a new impact brief; it goes live once the programme team approves
 * it (L-ONES.rules/5). Error: `brief_invalid` (V-FIELDS.one/4).
 */
export async function POST(request: NextRequest) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return oneBrief(me, await objectBody(request));
}
