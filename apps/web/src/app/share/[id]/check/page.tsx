import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import type { ConfigResponse } from "@/lib/contracts";
import { currentUser } from "@/server/auth/current";
import { isOn, switchStates } from "@/server/killswitch";
import { isKey, publicConfig } from "@/server/share";

import { CheckIt } from "./check-it";

export const metadata: Metadata = { title: "Check it" };
export const dynamic = "force-dynamic";

/**
 * S-05 "Check it, then send it", `/share/:draftId/check` (P-ROUTES). The owner's draft only: the screen reads it
 * through the API, so a draft that is not theirs answers 404 there. The sorting lists, the declaration and the upload
 * limits come with the page (A-API.config); the screen asks for them itself if this read fails. So does the
 * `files.blackout` switch, which decides whether a file row offers "Hide it for me".
 */
export default async function CheckPage({ params }: { params: Promise<{ id: string }> }) {
  const id = (await params).id;
  const me = await currentUser();
  if (!me) redirect(`/sign-in?next=${encodeURIComponent(`/share/${id}/check`)}`);
  if (!isKey(id)) notFound();
  const [config, states] = await Promise.all([
    publicConfig().catch((): ConfigResponse | null => null),
    switchStates().catch(() => new Map<string, "on" | "off">()),
  ]);
  // "Hide it for me" waits for `files.blackout` (off at launch, DEC-107); an unread switch counts as off.
  return <CheckIt draftId={id} config={config} blackout={isOn(states, "files.blackout")} />;
}
