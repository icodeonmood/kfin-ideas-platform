import type { NextRequest } from "next/server";

import { inboxPost } from "@/server/inbox-route";

/** POST /api/inbox/{id}/unread: "Mark unread" (S-H5). */
export async function POST(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  return inboxPost((await params).id, "unread");
}
