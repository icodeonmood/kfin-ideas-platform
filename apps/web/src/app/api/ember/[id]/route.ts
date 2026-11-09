import { NextResponse } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { emberIssue } from "@/server/ember";
import { asResponse } from "@/server/http";

/** GET /api/ember/{id} — A sent issue for anyone; a draft only for the chair and admins (the worker checks). */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("signed_in");
  if (me instanceof NextResponse) return me;
  try {
    return NextResponse.json(await emberIssue(me, (await params).id));
  } catch (err) {
    return asResponse(err);
  }
}
