import type { NextRequest } from "next/server";

import { teamupGet, teamupWrite } from "@/server/teamup";

type Ctx = { params: Promise<{ id: string }> };

const mine = teamupGet((id) => `/internal/ideas/${id}/team-up`);
const send = teamupWrite("POST", (id) => `/internal/ideas/${id}/team-up`, ["note", "brought_idea_ids", "draft_id"]);

/** GET /api/ideas/{id}/team-up: this idea's team-up state for the signed-in person ("Waiting for Ravi"). */
export async function GET(request: NextRequest, ctx: Ctx) {
  return mine(request, ctx);
}

/** POST /api/ideas/{id}/team-up: ask the lead to team up, with a note and any ideas brought (L-TEAMUP). */
export async function POST(request: NextRequest, ctx: Ctx) {
  return send(request, ctx);
}
