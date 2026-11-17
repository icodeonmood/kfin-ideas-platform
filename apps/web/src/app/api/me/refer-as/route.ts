import { NextResponse, type NextRequest } from "next/server";

import { parseReferAs } from "@/lib/refer-as";
import { signedIn } from "@/server/auth/authorize";
import { readJson } from "@/server/http";
import { getReferAs, setReferAs } from "@/server/refer-as";

/** GET /api/me/refer-as → { refer_as: "she" | "he" | "they" | "unset" }: how I want to be referred to (BLD-C111). */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return NextResponse.json(await getReferAs(me));
}

/** PUT /api/me/refer-as { refer_as: "she" | "he" | "they" | "unset" } → the same. "Prefer not to say" is "unset". */
export async function PUT(request: NextRequest) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const value = parseReferAs((await readJson(request)).refer_as);
  if (value === undefined) return NextResponse.json({ error: "refer_as_invalid" }, { status: 400 });
  return NextResponse.json(await setReferAs(me, value));
}
