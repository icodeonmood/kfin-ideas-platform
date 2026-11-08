import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { myIdeas } from "@/server/ideas";

/** GET /api/me/ideas — my ideas with stage, next step and date, and the ideas I joined (AT-B7-02). */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await myIdeas(me), { headers: { "Cache-Control": "no-store" } });
  } catch (err) {
    return asResponse(err);
  }
}
