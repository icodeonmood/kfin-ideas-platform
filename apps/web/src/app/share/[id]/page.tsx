import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { captureFirstOn, isMergedDraft, UUID } from "@/server/drafts";
import { composeFlags, interviewPlace } from "@/server/flag-events";

import { Compose } from "../compose";
import "../compose.css";

export const metadata: Metadata = { title: "Share a problem" };
export const dynamic = "force-dynamic";

/** S-04B, Tell it: the conversation, from S-04's first message, Home's prompt or a saved draft (`/share/:draftId`).
 * A draft merged into another idea has nothing more to tell: it opens on Check it, read-only (J-SIMILAR/6a,
 * BLD-C155). If that cannot be read here, Tell it's own load sends it there too. The S1 and S3 variants come from
 * lane A's reader on the server (the exposure logged as the screen renders), and S1's questions carry on from where
 * the draft's place is kept (P-DECISIONS.experiments, BLD-A216, BLD-C170, C172). Capture first (DEC-125) is `ai.all`
 * off, read as the "taking a break" banner reads it (BLD-C212). */
export default async function TellItConversation({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const id = (await params).id;
  if (!UUID.test(id)) notFound();
  if (await isMergedDraft(me, id).catch(() => false)) redirect(`/share/${id}/check`);
  const firstName = me.name.trim().split(/\s+/)[0] ?? me.name;
  const [flags, place, capture] = await Promise.all([
    composeFlags(me, "S-04B"),
    interviewPlace(me.id, id),
    captureFirstOn(),
  ]);
  return (
    <Compose firstName={firstName} draftId={id} flags={flags} interviewPlace={place} captureFirst={capture} />
  );
}
