import { NextResponse, type NextRequest } from "next/server";

import { signedIn } from "@/server/auth/authorize";
import { likePost, objectBody } from "@/server/wall";

/** PUT /api/ones/posts/{id}/like — {liked: boolean}: like or unlike a One's post; returns the new count. */
export async function PUT(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  return likePost(me, (await params).id, await objectBody(request));
}
