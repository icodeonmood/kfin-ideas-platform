import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { presentationForCommittee } from "@/server/committee";
import { asResponse } from "@/server/http";

/** GET /api/committee/presentations/{id} — the committee's view of a presentation (§4.7). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("decide");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await presentationForCommittee(me, (await params).id), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (err) {
    return asResponse(err);
  }
}
