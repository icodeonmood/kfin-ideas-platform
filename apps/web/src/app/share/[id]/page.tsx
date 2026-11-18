import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { isMergedDraft, UUID } from "@/server/drafts";

import { Compose } from "../compose";
import "../compose.css";

export const metadata: Metadata = { title: "Share a problem" };
export const dynamic = "force-dynamic";

/** S-04B, Tell it: the conversation, from S-04's first message, Home's prompt or a saved draft (`/share/:draftId`).
 * A draft merged into another idea has nothing more to tell: it opens on Check it, read-only (J-SIMILAR/6a,
 * BLD-C155). If that cannot be read here, Tell it's own load sends it there too. */
export default async function TellItConversation({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const id = (await params).id;
  if (!UUID.test(id)) notFound();
  if (await isMergedDraft(me, id).catch(() => false)) redirect(`/share/${id}/check`);
  const firstName = me.name.trim().split(/\s+/)[0] ?? me.name;
  return <Compose firstName={firstName} draftId={id} />;
}
