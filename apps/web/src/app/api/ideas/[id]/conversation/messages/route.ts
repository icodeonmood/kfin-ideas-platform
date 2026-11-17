import type { NextRequest } from "next/server";

import { postMessage } from "@/server/convo";

/** POST /api/ideas/{id}/conversation/messages — `{ text, file_ids?, mentions? }` (L-CONVO/5–7). */
export async function POST(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  return postMessage(request, ctx);
}
