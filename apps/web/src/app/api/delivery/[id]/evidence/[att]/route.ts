import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { evidenceContent, removeEvidence } from "@/server/delivery";
import { asResponse } from "@/server/http";

/**
 * GET /api/delivery/{id}/evidence/{att} — open a clean evidence file (BLD-131). Only people who can see the
 * delivery; anything not clean is refused. Served as a download that cannot run in this origin; logged by the
 * worker.
 */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string; att: string }> },
) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    const res = await evidenceContent(me, p.id, p.att);
    if (!res.ok) {
      const status = res.status === 404 ? 404 : 403;
      return NextResponse.json({ error: status === 404 ? "not_found" : "not_available" }, { status });
    }
    return new NextResponse(res.body, {
      status: 200,
      headers: {
        "Content-Type": res.headers.get("content-type") ?? "application/octet-stream",
        "Content-Disposition": `attachment; filename="${p.att}"`,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
      },
    });
  } catch (err) {
    return asResponse(err);
  }
}

/** DELETE /api/delivery/{id}/evidence/{att} — the person who added it, or an admin, before the delivery closes. */
export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string; att: string }> },
) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  try {
    const p = await params;
    return NextResponse.json(await removeEvidence(me, p.id, p.att));
  } catch (err) {
    return asResponse(err);
  }
}
