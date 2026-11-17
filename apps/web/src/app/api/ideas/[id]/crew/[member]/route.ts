import type { NextRequest } from "next/server";

import { teamupWrite } from "@/server/teamup";

const remove = teamupWrite("DELETE", (id, member) => `/internal/ideas/${id}/crew/${member}`);

/** DELETE /api/ideas/{id}/crew/{member}: the lead removes a member, by their person id (L-TEAMUP.rules/11). */
export async function DELETE(request: NextRequest, ctx: { params: Promise<{ id: string; member: string }> }) {
  return remove(request, ctx);
}
