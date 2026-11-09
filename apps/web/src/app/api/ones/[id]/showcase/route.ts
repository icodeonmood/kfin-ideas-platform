import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { showcaseFor } from "@/server/ones";

/** GET /api/ones/{id}/showcase — A One's Showcase brief, for the committee (DEC-086). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const auth = await authorize("view_ones_console");
  if (auth instanceof NextResponse) return auth;
  try {
    return NextResponse.json(await showcaseFor((await params).id));
  } catch (err) {
    return asResponse(err);
  }
}
