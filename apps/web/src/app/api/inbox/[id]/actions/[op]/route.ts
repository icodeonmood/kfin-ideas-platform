import type { NextRequest } from "next/server";

import { inboxError, inboxPost } from "@/server/inbox-route";

/** POST /api/inbox/{id}/actions/{op}: one of the item's server operations (E-ENTITIES `Action.op`), run by the lane
 * that owns it (`notify.ops` in the worker). The item must be the person's and must offer the op. */
export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string; op: string }> },
) {
  const { id, op } = await params;
  if (!/^[a-z_][a-z_.]{0,59}$/.test(op)) return inboxError("not_found", 404);
  return inboxPost(id, `actions/${op}`);
}
