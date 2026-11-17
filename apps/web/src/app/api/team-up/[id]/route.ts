import type { NextRequest } from "next/server";

import { teamupGet, teamupWrite } from "@/server/teamup";

type Ctx = { params: Promise<{ id: string }> };

const read = teamupGet((id) => `/internal/team-up/${id}`);
const withdraw = teamupWrite("DELETE", (id) => `/internal/team-up/${id}`);

/** GET /api/team-up/{id}: a team-up or draft merge request, for the requester or the idea's lead (S-H2B). */
export async function GET(request: NextRequest, ctx: Ctx) {
  return read(request, ctx);
}

/** DELETE /api/team-up/{id}: the requester withdraws a waiting request. */
export async function DELETE(request: NextRequest, ctx: Ctx) {
  return withdraw(request, ctx);
}
