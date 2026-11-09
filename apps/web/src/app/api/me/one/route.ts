import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { myOne } from "@/server/ones";

/** GET /api/me/one — The person's own One record, if they are a One. */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json({ one: await myOne(me) });
  } catch (err) {
    return asResponse(err);
  }
}
