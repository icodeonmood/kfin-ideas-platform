import { NextResponse, type NextRequest } from "next/server";

import { accessible } from "@/server/attachments";
import { authorize } from "@/server/auth/authorize";

/** GET /api/attachments/{id}/status — where a file is in its checks (owner or review roles). */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("open_attachments");
  if (me instanceof NextResponse) return me;
  const row = await accessible(me, (await params).id);
  if (!row) return NextResponse.json({ error: "not_found" }, { status: 404 });
  return NextResponse.json(
    { id: row.id, name: row.name, bytes: Number(row.bytes), state: row.state, rejection: row.rejection },
    { headers: { "Cache-Control": "no-store" } },
  );
}
