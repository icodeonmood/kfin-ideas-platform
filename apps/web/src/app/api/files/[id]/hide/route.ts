import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { hideFile } from "@/server/files";

/** POST /api/files/{id}/hide ("Hide it for me", L-HIDE.files/3). Black-out is not built (DEC-107): while
 * `files.blackout` is off this answers `not_available` with the switch's notice, checked here on every request. */
export async function POST(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  return hideFile(me, (await params).id);
}
