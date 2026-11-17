import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { fileItem, removeFile } from "@/server/files";

type Ctx = { params: Promise<{ id: string }> };

/** GET /api/files/{id}: the FileItem, for a screen following the check. Anyone the worker does not let see it: 404. */
export async function GET(_request: NextRequest, { params }: Ctx) {
  const me = await authorize("open_attachments");
  if (me instanceof NextResponse) return me;
  return fileItem(me, (await params).id);
}

/** DELETE /api/files/{id} ("Remove", "Remove file"): the person who added it, in any state. Never behind a switch:
 * removing a file only ever protects someone (DEC-107: the review desk may ask for it). */
export async function DELETE(_request: NextRequest, { params }: Ctx) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  return removeFile(me, (await params).id);
}
