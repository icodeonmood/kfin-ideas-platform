import type { NextRequest } from "next/server";

import { deleteMessage } from "@/server/convo";

/** DELETE /api/ideas/{id}/conversation/messages/{entryId} — the sender's own message, within 5 minutes (L-CONVO/10). */
export async function DELETE(
  request: NextRequest,
  ctx: { params: Promise<{ id: string; entryId: string }> },
) {
  return deleteMessage(request, ctx);
}
