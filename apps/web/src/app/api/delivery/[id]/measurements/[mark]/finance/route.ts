import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { financeConfirm } from "@/server/delivery";
import { asResponse } from "@/server/http";

/** POST /api/delivery/{id}/measurements/{mark}/finance — An admin records Finance's confirmation of the money figure (DEC-071). */
export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string; mark: string }> },
) {
  const me = await authorize("manage_delivery");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await financeConfirm(me, p.id, p.mark));
  } catch (err) {
    return asResponse(err);
  }
}
