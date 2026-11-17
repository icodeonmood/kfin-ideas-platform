import type { NextRequest } from "next/server";

import { teamupGet } from "@/server/teamup";

const read = teamupGet((id) => `/internal/ideas/${id}/team-up/draft-note`);

/** GET /api/ideas/{id}/team-up/draft-note: the pre-filled note and the person's own ideas that can be brought. */
export async function GET(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  return read(request, ctx);
}
