import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { flagsFor } from "@/server/flags";
import { log } from "@/server/log";
import { publicConfig } from "@/server/share";

export const dynamic = "force-dynamic";

/** GET /api/config (A-API.config): the promises the copy names, the sorting lists and the declaration (lane C,
 * read on the server from the company repo's rules, so a change there needs no release), and this person's S1 to S3
 * variants (L-AUDIT.flags). Reading it logs no exposure: a screen logs one when it shows a variant (`flagVariant`).
 * If the worker cannot give the config, the person's flags still come back and the rest is left out (BLD-A216): a
 * screen keeps its own defaults. */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const [config, flags] = await Promise.all([
    publicConfig().catch(() => {
      log.warn("config.promises_unavailable");
      return undefined;
    }),
    flagsFor(me.id),
  ]);
  return NextResponse.json(config ? { ...config, flags } : { flags }, {
    headers: { "Cache-Control": "private, no-store" },
  });
}
