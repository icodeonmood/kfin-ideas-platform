import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { Conversation } from "@/components/convo/conversation";
import { switchesFor } from "@/lib/killswitch-routes";
import { currentUser } from "@/server/auth/current";
import { readConversation } from "@/server/convo";
import { isOn, switchStates } from "@/server/killswitch";

export const metadata: Metadata = { title: "Conversation" };
export const dynamic = "force-dynamic";

/** Whether writing here is paused: the switches on the message route (BLD-F058), read as the proxy reads them. A read
 * that fails counts as paused (fail closed); it only keeps "Say hello" from putting the cursor in the box (BLD-F069). */
async function writingPaused(id: string): Promise<boolean> {
  try {
    const states = await switchStates();
    return switchesFor("POST", `/api/ideas/${encodeURIComponent(id)}/conversation/messages`).some(
      (s) => !isOn(states, s),
    );
  } catch {
    return true;
  }
}

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
  return <Conversation initial={view} ideaId={id} paused={await writingPaused(id)} />;
}
