/** The Inbox's write routes, one shape: check the person and the item ID, ask the worker, pass its answer on with
 * the error envelope of A-API.conventions/2. */
import { NextResponse } from "next/server";

import { signedIn } from "./auth/authorize";
import { inboxWrite, isItemId } from "./inbox";

const MESSAGES: Record<string, string> = {
  needs_you: "This still needs you, so it stays in your Inbox until it's done.",
  not_found: "We couldn't find that in your Inbox.",
  not_offered: "That isn't something you can do from here.",
  not_available: "That can't be done from the Inbox just yet. Open the idea to do it there.",
};

export async function inboxPost(id: string | null, verb: string): Promise<NextResponse> {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  if (id !== null && !isItemId(id)) return inboxError("not_found", 404);
  const res = await inboxWrite(me, id, verb);
  const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) {
    const code = typeof body.error === "string" ? body.error : "unavailable";
    return inboxError(code, res.status >= 500 ? 503 : res.status);
  }
  return NextResponse.json(body, { headers: { "Cache-Control": "no-store" } });
}

export function inboxError(code: string, status: number): NextResponse {
  const message = MESSAGES[code] ?? "We couldn't do that just now. Please try again in a minute.";
  return NextResponse.json({ error: { code, message } }, { status });
}
