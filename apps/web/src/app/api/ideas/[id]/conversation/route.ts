import type { NextRequest } from "next/server";

import { getConversation } from "@/server/convo";

/** GET /api/ideas/{id}/conversation — the idea's one conversation, as this person may read it (L-CONVO). */
export async function GET(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  return getConversation(request, ctx);
}
