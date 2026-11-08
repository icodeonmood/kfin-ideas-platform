import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { markRead } from "@/server/inbox";

/** POST /api/inbox/{id}/read — mark one of my messages read (in-app only; email opens are never tracked). */
export async function POST(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const ok = await markRead(me, (await params).id);
  return ok
    ? new NextResponse(null, { status: 204 })
    : NextResponse.json({ error: "not_found" }, { status: 404 });
}
