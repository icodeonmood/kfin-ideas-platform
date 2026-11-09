import { NextResponse } from "next/server";

import { appealView } from "@/server/appeals";
import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";

/** GET /api/appeals/{id} — the panel's blind view of an appeal (§4.12 step 2); the worker checks the panel. */

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("hear_appeals");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await appealView(me, (await params).id));
  } catch (err) {
    return asResponse(err);
  }
}
