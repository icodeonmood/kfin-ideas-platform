import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { flagsFor } from "@/server/flags";
import { log } from "@/server/log";
import { promises } from "@/server/promises";

export const dynamic = "force-dynamic";

/** GET /api/config (A-API.config) — the numbers the screens show and keep to (P-PRODUCT.promises, from the company
 * repo's rules/promises.md, BLD-A181) and this person's S1 to S3 variants (L-AUDIT.flags). Reading it logs no
 * exposure: a screen logs one when it shows a variant (`flagVariant`). If the worker cannot give the promises, the
 * person's flags still come back and `promises` is left out (BLD-A216): a screen keeps its own defaults. */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const [values, flags] = await Promise.all([
    promises().catch(() => {
      log.warn("config.promises_unavailable");
      return undefined;
    }),
    flagsFor(me.id),
  ]);
  return NextResponse.json(values ? { promises: values, flags } : { flags }, {
    headers: { "Cache-Control": "private, no-store" },
  });
}
