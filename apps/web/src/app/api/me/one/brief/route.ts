import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { asResponse, readJson } from "@/server/http";
import { proposeBrief } from "@/server/ones";

/** POST /api/me/one/brief — A One proposes their impact brief; the committee approves it (DEC-073). */
export async function POST(request: NextRequest) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await proposeBrief(me, await readJson(request)), { status: 201 });
  } catch (err) {
    return asResponse(err);
  }
}
