import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { versions } from "@/server/share";

/** GET /api/ideas/{id}/versions: "Draft history" (L-SUBMIT.edit/4). The worker shows it to the sharer, the review
 * desk and the Ones Committee only, and answers 404 to anyone else. */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return versions(me, (await params).id);
}
