import { NextResponse, type NextRequest } from "next/server";

import { MAX_UPLOAD_BYTES, upload } from "@/server/attachments";
import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";

/** POST /api/submissions/{id}/attachments (multipart, field "file") — one research file into quarantine. */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  // Refuse oversize uploads before reading the body (the proxy would otherwise buffer and truncate it).
  const length = Number(request.headers.get("content-length") ?? "0");
  if (length > MAX_UPLOAD_BYTES + 64 * 1024)
    return NextResponse.json({ error: "file_too_large" }, { status: 413 });
  const form = await request.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) return NextResponse.json({ error: "file_required" }, { status: 400 });
  try {
    return NextResponse.json(await upload(me, (await params).id, file), { status: 201 });
  } catch (err) {
    return asResponse(err);
  }
}
