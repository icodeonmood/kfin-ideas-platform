import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { publicConfig } from "@/server/share";

/** GET /api/config (A-API.config): the promises the copy names and the sorting lists. Read on the server from the
 * company repo's rules, so a change there needs no release. */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return NextResponse.json(await publicConfig(), { headers: { "Cache-Control": "no-store" } });
}
