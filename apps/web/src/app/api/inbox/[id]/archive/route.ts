import type { NextRequest } from "next/server";

import { inboxPost } from "@/server/inbox-route";

/** POST /api/inbox/{id}/archive: hides it from All. Error `needs_you` while it still waits on the person
 * (A-API.inbox, L-INBOX.rules/5). */
export async function POST(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return inboxPost((await params).id, "archive");
}
