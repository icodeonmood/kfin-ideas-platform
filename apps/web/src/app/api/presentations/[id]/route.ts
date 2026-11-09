import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { presentationForContributor } from "@/server/committee";
import { asResponse } from "@/server/http";

/** GET /api/presentations/{id} — a contributor's invitation to present (§4.7 step 1). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("present");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await presentationForContributor(me, (await params).id), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    return asResponse(err);
  }
}
