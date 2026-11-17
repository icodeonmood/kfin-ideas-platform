import type { NextRequest } from "next/server";

import { teamupGet, teamupWrite } from "@/server/teamup";

type Ctx = { params: Promise<{ id: string }> };

const read = teamupGet((id) => `/internal/drafts/${id}/merge-request`);
const ask = teamupWrite("POST", (id) => `/internal/drafts/${id}/merge-request`, ["other_idea_id", "note"]);
const withdraw = teamupWrite("DELETE", (id) => `/internal/drafts/${id}/merge-request`);

/** GET /api/drafts/{id}/merge-request: the draft's merge request and what Check it shows (L-MERGE.request). */
export async function GET(request: NextRequest, ctx: Ctx) {
  return read(request, ctx);
}

/** POST /api/drafts/{id}/merge-request: "Ask {lead} to merge mine in". Only the lead can accept. */
export async function POST(request: NextRequest, ctx: Ctx) {
  return ask(request, ctx);
}

/** DELETE /api/drafts/{id}/merge-request: withdraw; the draft returns to normal. */
export async function DELETE(request: NextRequest, ctx: Ctx) {
  return withdraw(request, ctx);
}
