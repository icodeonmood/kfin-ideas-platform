import { NextResponse } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { messagesFor } from "@/server/inbox";

/** GET /api/inbox — my messages, newest first. */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return NextResponse.json({ messages: await messagesFor(me) }, { headers: { "Cache-Control": "no-store" } });
}
