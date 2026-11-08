import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse, readJson } from "@/server/http";
import { createDraft } from "@/server/submissions";

/** POST /api/submissions {mode, canvas?} — start a draft (§8). */
export async function POST(request: NextRequest) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const body = await readJson(request);
  const mode = body.mode === "quick" ? "quick" : "full";
  try {
    return NextResponse.json(await createDraft(me, mode, body.canvas), { status: 201 });
  } catch (err) {
    return asResponse(err);
  }
}
