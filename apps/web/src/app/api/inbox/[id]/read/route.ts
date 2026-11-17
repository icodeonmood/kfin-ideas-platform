import type { NextRequest } from "next/server";

import { inboxPost } from "@/server/inbox-route";

/** POST /api/inbox/{id}/read: opening an item marks it read (L-INBOX.rules/3). Returns every tab's count, so every
 * count on the screen changes at once (S-H5.rules/4). */
export async function POST(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return inboxPost((await params).id, "read");
}
