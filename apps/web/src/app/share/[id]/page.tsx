import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { UUID } from "@/server/drafts";
import { composeFlags, interviewPlace } from "@/server/flag-events";

import { Compose } from "../compose";
import "../compose.css";

export const metadata: Metadata = { title: "Share a problem" };
export const dynamic = "force-dynamic";

/** S-04B, Tell it: the conversation, from S-04's first message, Home's prompt or a saved draft (`/share/:draftId`).
 * The S1 and S3 variants come from lane A's reader on the server (the exposure logged as the screen renders), and
 * S1's questions carry on from where the draft's place is kept (P-DECISIONS.experiments, BLD-A216, BLD-C170, C172). */
export default async function TellItConversation({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const id = (await params).id;
  if (!UUID.test(id)) notFound();
  const firstName = me.name.trim().split(/\s+/)[0] ?? me.name;
  const [flags, place] = await Promise.all([composeFlags(me, "S-04B"), interviewPlace(me.id, id)]);
  return <Compose firstName={firstName} draftId={id} flags={flags} interviewPlace={place} />;
}
