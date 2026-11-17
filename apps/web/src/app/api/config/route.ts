import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { flagsFor } from "@/server/flags";
import { promises } from "@/server/promises";

export const dynamic = "force-dynamic";

/** GET /api/config (A-API.config) — the numbers the screens show and keep to (P-PRODUCT.promises, from the company
 * repo's rules/promises.md, BLD-A181) and this person's S1 to S3 variants (L-AUDIT.flags). Reading it logs no
 * exposure: a screen logs one when it shows a variant (`flagVariant`). */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const [values, flags] = await Promise.all([promises(), flagsFor(me.id)]);
  return NextResponse.json({ promises: values, flags }, { headers: { "Cache-Control": "private, no-store" } });
}
