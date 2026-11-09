import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { asResponse, readJson } from "@/server/http";
import { addMessage } from "@/server/ones";

/** POST /api/ones/proposals/{id}/messages — A message for a One's tier change: committee, CEO or an invited colleague (DEC-084). */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await addMessage(me, (await params).id, await readJson(request)), {
      status: 201,
    });
  } catch (err) {
    return asResponse(err);
  }
}
