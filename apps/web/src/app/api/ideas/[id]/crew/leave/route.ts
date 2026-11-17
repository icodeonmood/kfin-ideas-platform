import type { NextRequest } from "next/server";

import { teamupWrite } from "@/server/teamup";

const leave = teamupWrite("POST", (id) => `/internal/ideas/${id}/crew/leave`);

/** POST /api/ideas/{id}/crew/leave: a crew member leaves; the lead stays (L-TEAMUP.rules/11). */
export async function POST(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  return leave(request, ctx);
}
