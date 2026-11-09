import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { workingGroup } from "@/server/committee";
import { asResponse } from "@/server/http";

/** GET /api/working-groups/{id} — a working group's page (members, the sponsor and the committee). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("signed_in");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await workingGroup(me, (await params).id), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    return asResponse(err);
  }
}
