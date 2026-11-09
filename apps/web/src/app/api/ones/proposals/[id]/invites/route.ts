import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse, readJson } from "@/server/http";
import { invitePeer } from "@/server/ones";

/** POST /api/ones/proposals/{id}/invites — Invite a colleague to write a message for a One's tier change. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("decide_ones");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await invitePeer(me, (await params).id, await readJson(request)));
  } catch (err) {
    return asResponse(err);
  }
}
