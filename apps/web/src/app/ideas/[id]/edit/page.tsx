import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import type { ConfigResponse } from "@/lib/contracts";
import { currentUser } from "@/server/auth/current";
import { isOn, switchStates } from "@/server/killswitch";
import { isKey, publicConfig } from "@/server/share";

import { EditIdea } from "./edit-idea";

export const metadata: Metadata = { title: "Edit" };
export const dynamic = "force-dynamic";

/**
 * S-06B "Edit after sharing", `/ideas/:id/edit` (P-ROUTES; from S-06's "Edit it", and back to S-06 with Save or
 * Cancel). The sharer's own idea only: the screen reads it through `GET /api/ideas/:id/edit`, so an idea that is not
 * theirs answers 404 there. The sorting lists and the upload limits come with the page (A-API.config); the screen asks
 * for them itself if this read fails. So does the `files.blackout` switch, which decides whether a file row offers
 * "Hide it for me", as on Check it.
 */
export default async function EditPage({ params }: { params: Promise<{ id: string }> }) {
  const id = (await params).id;
  const me = await currentUser();
  if (!me) redirect(`/sign-in?next=${encodeURIComponent(`/ideas/${id}/edit`)}`);
  if (!isKey(id)) notFound();
  const [config, states] = await Promise.all([
    publicConfig().catch((): ConfigResponse | null => null),
    switchStates().catch(() => new Map<string, "on" | "off">()),
  ]);
  // "Hide it for me" waits for `files.blackout` (off at launch, DEC-107); an unread switch counts as off.
  return <EditIdea ideaId={id} config={config} blackout={isOn(states, "files.blackout")} />;
}
