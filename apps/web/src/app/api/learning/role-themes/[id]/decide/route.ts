import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { decideRoleThemes } from "@/server/delivery";
import { asResponse, readJson } from "@/server/http";

/** POST /api/learning/role-themes/{id}/decide — Approve or decline one role's friction themes (BLD-139). Only
 * approved themes show on the lenses page; nothing else changes. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("review_learning");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await decideRoleThemes(me, p.id, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
