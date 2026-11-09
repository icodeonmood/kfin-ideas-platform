import { NextResponse, type NextRequest } from "next/server";

import { MAX_UPLOAD_BYTES } from "@/server/attachments";
import { authorize } from "@/server/auth/authorize";
import { uploadEvidence } from "@/server/delivery";
import { asResponse } from "@/server/http";

/**
 * POST /api/delivery/{id}/evidence (multipart, field "file") — an evidence file into quarantine (BLD-131). The
 * owner or an admin; the worker checks again. Nobody can open it until the virus and personal-data checks pass.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("work_delivery");
  if (me instanceof NextResponse) return me;
  const header = request.headers.get("content-length");
  if (header === null) return NextResponse.json({ error: "length_required" }, { status: 411 });
  if (Number(header) > MAX_UPLOAD_BYTES + 64 * 1024)
    return NextResponse.json({ error: "file_too_large" }, { status: 413 });
  const form = await request.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) return NextResponse.json({ error: "file_required" }, { status: 400 });
  try {
    return NextResponse.json(await uploadEvidence(me, (await params).id, file), { status: 201 });
  } catch (err) {
    return asResponse(err);
  }
}
