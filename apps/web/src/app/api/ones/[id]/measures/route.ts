import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse, readJson } from "@/server/http";
import { setMeasures } from "@/server/ones";

/** PUT /api/ones/{id}/measures — Measured impact for a One: values and fixed units only (DEC-071). */
export async function PUT(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("carry_out_ones");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await setMeasures(me, (await params).id, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
