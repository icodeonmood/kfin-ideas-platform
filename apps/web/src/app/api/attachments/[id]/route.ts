import { NextResponse, type NextRequest } from "next/server";

import { accessible } from "@/server/attachments";
import { auditIp, authorize } from "@/server/auth/authorize";
import { getDb } from "@/server/db";
import { workerFetch } from "@/server/worker";

/**
 * GET /api/attachments/{id} — open a clean file (§8: clean files only; RBAC; every download logged).
 * Anything not clean answers 403, to everyone (AT-B3-07). Served as a download that cannot run in this origin.
 */
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("open_attachments");
  if (me instanceof NextResponse) return me;
  const id = (await params).id;
  const row = await accessible(me, id);
  if (!row) return NextResponse.json({ error: "not_found" }, { status: 404 });
  if (row.state !== "clean")
    return NextResponse.json({ error: "not_available", state: row.state }, { status: 403 });
  // The timer also bounds the body stream, so allow for a 20 MB file on a slow link.
  const res = await workerFetch(`/internal/attachments/${encodeURIComponent(id)}/content`, {
    signal: AbortSignal.timeout(300_000),
  });
  if (!res.ok) return NextResponse.json({ error: "not_available" }, { status: 403 });
  await getDb()
    .insertInto("audit_log")
    .values({
      actor: `user:${me.id}`,
      action: "attachment.download",
      entity: `attachment:${id}`,
      ip: auditIp(request.headers),
    })
    .execute();
  const safeName = row.name.replace(/[^A-Za-z0-9._ -]/g, "_").slice(0, 120) || "file";
  return new NextResponse(res.body, {
    status: 200,
    headers: {
      "Content-Type": row.mime ?? "application/octet-stream",
      "Content-Disposition": `attachment; filename="${safeName}"`,
      "X-Content-Type-Options": "nosniff",
      "Content-Security-Policy": "sandbox; default-src 'none'",
      "Cache-Control": "private, no-store",
    },
  });
}
