import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { editPage, jsonBody, saveEdit } from "@/server/share";

type Ctx = { params: Promise<{ id: string }> };

/** GET /api/ideas/{id}/edit: the edit page for the sharer, in the edit window (S-06B, L-SUBMIT.edit). */
export async function GET(_request: NextRequest, { params }: Ctx) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  return editPage(me, (await params).id);
}

/** PATCH /api/ideas/{id}/edit: Save changes (A-API `PATCH /ideas/:id`); each save is a version. Refused with
 * `edit_window_closed` once the review desk opens it. Behind `submissions`. */
export async function PATCH(request: NextRequest, { params }: Ctx) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  return saveEdit(me, (await params).id, await jsonBody(request));
}
