import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { inviteView } from "@/server/ones";

/** GET /api/ones/proposals/{id}/invite — What an invited colleague (or the CEO) is asked to write for a One's tier change. */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await inviteView(me, (await params).id));
  } catch (err) {
    return asResponse(err);
  }
}
