import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { Conversation } from "@/components/convo/conversation";
import { currentUser } from "@/server/auth/current";
import { readConversation } from "@/server/convo";

export const metadata: Metadata = { title: "Conversation" };
export const dynamic = "force-dynamic";

/**
 * S-08, an idea's conversation, at `/ideas/:id/conversation` (P-ROUTES). The worker decides who may read it: the
 * sharer, the crew, the build team, the review desk, the Ones Committee and a mentioned person; anyone else gets the
 * not-found page, never a "you can't see this" (L-CONVO/2).
 */
export default async function ConversationPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const id = (await params).id;
  const view = await readConversation(me, id);
  if (!view) notFound();
  return <Conversation initial={view} ideaId={id} />;
}
