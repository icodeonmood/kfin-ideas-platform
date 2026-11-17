import type { NextRequest } from "next/server";

import { teamupWrite } from "@/server/teamup";

const answer = teamupWrite("POST", (id) => `/internal/team-up/${id}/answer`, ["answer", "reason"]);

/** POST /api/team-up/{id}/answer: the idea's lead answers Merge it, Team up only or Decline (S-H2B). */
export async function POST(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  return answer(request, ctx);
}
