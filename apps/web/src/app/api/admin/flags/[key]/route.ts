import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { FlagError, setFlag } from "@/server/flags";
import { readJson } from "@/server/http";

/** PUT /api/admin/flags/{key} {state, alternative_percent, reason} — an admin sets an experiment (L-AUDIT.flags);
 * audited. */
export async function PUT(request: NextRequest, { params }: { params: Promise<{ key: string }> }) {
  const me = await authorize("manage_flags");
  if (me instanceof NextResponse) return me;
  const body = await readJson(request);
  try {
    await setFlag({
      key: (await params).key,
      state: body.state,
      alternativePercent: body.alternative_percent,
      reason: body.reason,
      actorUserId: me.id,
    });
  } catch (err) {
    if (err instanceof FlagError) return NextResponse.json(err.body(), { status: err.status });
    throw err;
  }
  return new NextResponse(null, { status: 204 });
}
