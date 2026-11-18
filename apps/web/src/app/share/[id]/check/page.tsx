import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import type { ConfigResponse } from "@/lib/contracts";
import { currentUser } from "@/server/auth/current";
import { quietVariant } from "@/server/flag-events";
import { isOn, switchStates } from "@/server/killswitch";
import { isKey, publicConfig } from "@/server/share";

import { CheckIt } from "./check-it";

export const metadata: Metadata = { title: "Check it" };
export const dynamic = "force-dynamic";

/**
 * S-05 "Check it, then send it", `/share/:draftId/check` (P-ROUTES). The owner's draft only: the screen reads it
 * through the API, so a draft that is not theirs answers 404 there. The sorting lists, the declaration and the upload
 * limits come with the page (A-API.config); the screen asks for them itself if this read fails. So does the
 * `files.blackout` switch, which decides whether a file row offers "Hide it for me". Flag S2 "Check first" comes from
 * lane A's reader on the server without an exposure: the screen logs that only when a close match on a fresh Check it
 * is the moment the other version changes the page (P-DECISIONS.experiments, BLD-A216, BLD-C173, BLD-C176). A flag
 * never fails or holds up the page.
 */
export default async function CheckPage({ params }: { params: Promise<{ id: string }> }) {
  const id = (await params).id;
  const me = await currentUser();
  if (!me) redirect(`/sign-in?next=${encodeURIComponent(`/share/${id}/check`)}`);
  if (!isKey(id)) notFound();
  const [config, states, s2] = await Promise.all([
    publicConfig().catch((): ConfigResponse | null => null),
    switchStates().catch(() => new Map<string, "on" | "off">()),
    quietVariant(me.id, "s2"),
  ]);
  // "Hide it for me" waits for `files.blackout` (off at launch, DEC-107); an unread switch counts as off.
  return (
    <CheckIt
      draftId={id}
      config={config}
      blackout={isOn(states, "files.blackout")}
      flags={{ checkFirst: s2 === "alternative" }}
    />
  );
}
